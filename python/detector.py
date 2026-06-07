import pandas as pd
from shapely.geometry import Point
import geopandas as gpd
import movingpandas as mpd
import numpy as np
import sys
import traceback
import argparse

from sklearn.neighbors import LocalOutlierFactor
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import HDBSCAN
from enum import Enum

def prepare_dataframe(path):
    df = pd.read_pickle(path)

    required_columns = {"dt", "lat", "lon"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Входной файл должен содержать столбцы: {sorted(required_columns)}. "
            f"Отсутствующие столбцы: {sorted(missing_columns)}"
        )


    df["dt"] = pd.to_datetime(df["dt"])
    df = df.sort_values("dt").drop_duplicates().copy()

    df["traj_id"] = "track_1"
    df["point_id"] = np.arange(len(df))

    df["geometry"] = df.apply(
        lambda row: Point(row["lon"], row["lat"]),
        axis=1
    )

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    traj = mpd.Trajectory(gdf, traj_id="track_1", t="dt")
    trajectory_collection = mpd.TrajectoryCollection([traj])

    trajectory_collection.add_speed(overwrite=True, units=("km", "h"))
    trajectory_collection.add_acceleration(overwrite=True)

    all_points = pd.concat(
        [traj.df for traj in trajectory_collection]
    ).reset_index()

    all_points = gpd.GeoDataFrame(
        all_points,
        geometry="geometry",
        crs="EPSG:4326"
    )

    result = all_points.dropna(
        subset=["lat", "lon", "speed", "acceleration"]
    ).copy()

    result_m = result.to_crs(3857).copy()
    result["x"] = result_m.geometry.x
    result["y"] = result_m.geometry.y

    return result

class Algorithm(Enum):
    LOF = "lof"
    ISO = "iso"
    HDBSCAN = "hdbscan"

# ===============window=================
def euclidean_distance(x1, y1, x2, y2):
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def point_line_distance(px, py, x1, y1, x2, y2):
    """
    Расстояние от точки P до отрезка AB в метрах.
    """
    A = np.array([x1, y1], dtype=float)
    B = np.array([x2, y2], dtype=float)
    P = np.array([px, py], dtype=float)

    AB = B - A
    AP = P - A
    ab2 = np.dot(AB, AB)

    if ab2 == 0:
      # Случай когда A и B совпадают
      return np.linalg.norm(P - A)

    # Направление проекции P на AB
    t = np.dot(AP, AB) / ab2
    t = np.clip(t, 0.0, 1.0)
    proj = A + t * AB
    return np.linalg.norm(P - proj)


def turning_angle(x_prev, y_prev, x, y, x_next, y_next):
    """
    Угол между векторами prev->cur и cur->next в градусах.
    """
    v1 = np.array([x - x_prev, y - y_prev], dtype=float)
    v2 = np.array([x_next - x, y_next - y], dtype=float)

    # Длины
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)

    if n1 == 0 or n2 == 0:
        return 0.0

    cosang = np.dot(v1, v2) / (n1 * n2)
    cosang = np.clip(cosang, -1.0, 1.0)
    return np.degrees(np.arccos(cosang))

def build_window_features_for_track(track_df, window=5):
    """
    Строит признаки для центральной точки окна.
    window должен быть нечётным.
    """
    assert window % 2 == 1, "window должен быть нечётным"

    half = window // 2
    track_df = track_df.sort_values("dt").reset_index(drop=True).copy()

    rows = []

    for i in range(half, len(track_df) - half):
        win = track_df.iloc[i - half:i + half + 1].copy()
        center = track_df.iloc[i]

        x = win["x"].to_numpy()
        y = win["y"].to_numpy()
        t = pd.to_datetime(win["dt"]).to_numpy()

        # dt между соседними точками в секундах
        dt_sec = np.diff(t).astype("timedelta64[ns]").astype(np.int64) / 1e9

        # расстояния между соседними точками
        dists = np.array([
            euclidean_distance(x[j], y[j], x[j + 1], y[j + 1])
            for j in range(len(win) - 1)
        ])

        # скорости по сегментам, м/с
        speeds = dists / dt_sec

        # ускорения по соседним сегментам
        if len(speeds) >= 2:
            accs = np.diff(speeds) / dt_sec[1:]
        else:
            accs = np.array([np.nan])

        # углы в окне
        angles = []
        for j in range(1, len(win) - 1):
            ang = turning_angle(
                x[j - 1], y[j - 1],
                x[j], y[j],
                x[j + 1], y[j + 1]
            )
            angles.append(ang)
        angles = np.array(angles, dtype=float)

        # центральная точка и её соседи
        c = half
        x_prev, y_prev = x[c - 1], y[c - 1]
        x_cur, y_cur = x[c], y[c]
        x_next, y_next = x[c + 1], y[c + 1]


        # Провереям расстояние от центральной точки до левого и правого соседа + расстояние между соседями напрямую
        dist_prev = euclidean_distance(x_prev, y_prev, x_cur, y_cur)
        dist_next = euclidean_distance(x_cur, y_cur, x_next, y_next)
        dist_skip = euclidean_distance(x_prev, y_prev, x_next, y_next)

        dt_prev = dt_sec[c - 1]
        dt_next = dt_sec[c]

        speed_prev = dist_prev / dt_prev if pd.notna(dt_prev) and dt_prev > 0 else np.nan
        speed_next = dist_next / dt_next if pd.notna(dt_next) and dt_next > 0 else np.nan

        # насколько центр далеко от краев окна
        center_deviation = point_line_distance(
            x_cur, y_cur,
            x[0], y[0],
            x[-1], y[-1]
        )

        # насколько путь через центральную точку длиннее прямого перехода
        spike_ratio = (
            (dist_prev + dist_next) / dist_skip
            if dist_skip > 0 else np.nan
        )

        # насколько прямолинеен путь
        path_length = np.nansum(dists)
        end_to_end = euclidean_distance(x[0], y[0], x[-1], y[-1])
        straightness = (
            path_length / end_to_end
            if end_to_end > 0 else np.nan
        )

        row = {
            "point_id": center["point_id"],
            "traj_id": center["traj_id"],
            "dt": center["dt"],
            "lat": center["lat"],
            "lon": center["lon"],
            "geometry": center["geometry"],

            # базовые признаки центральной точки
            "x": center["x"],
            "y": center["y"],
            "speed": center.get("speed", np.nan),
            "acceleration": center.get("acceleration", np.nan),

            # локальные признаки
            "dist_prev": dist_prev,
            "dist_next": dist_next,
            "dist_skip": dist_skip,
            "dt_prev": dt_prev,
            "dt_next": dt_next,
            "speed_prev_mps": speed_prev,
            "speed_next_mps": speed_next,
            "center_deviation": center_deviation,
            "spike_ratio": spike_ratio,

            # признаки окна
            "path_length": path_length,
            "end_to_end": end_to_end,
            "straightness": straightness,
            "mean_seg_dist": np.nanmean(dists),
            "max_seg_dist": np.nanmax(dists),
            "std_seg_dist": np.nanstd(dists),

            "mean_speed_mps": np.nanmean(speeds),
            "max_speed_mps": np.nanmax(speeds),
            "std_speed_mps": np.nanstd(speeds),

            "mean_acc_mps2": np.nanmean(accs),
            "max_acc_mps2": np.nanmax(np.abs(accs)) if len(accs) else np.nan,
            "std_acc_mps2": np.nanstd(accs),

            "mean_angle": np.nanmean(angles),
            "max_angle": np.nanmax(angles) if len(angles) else np.nan,
            "std_angle": np.nanstd(angles),
        }

        rows.append(row)

    return pd.DataFrame(rows)


def lof(df, features):
    part = df.copy()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(part[features])

    lof = LocalOutlierFactor(n_neighbors=30, contamination=0.1)

    labels = lof.fit_predict(X_scaled)
    scores = lof.negative_outlier_factor_

    part["flg"] = labels == -1
    part["score"] = scores

    return part.sort_index()


def iso(df, features):
    part = df.copy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(part[features])

    iso = IsolationForest(
        n_estimators=300,
        contamination=0.06,
        random_state=42,
    )

    labels = iso.fit_predict(X_scaled)
    scores = iso.decision_function(X_scaled)

    part["flg"] = labels == -1
    part["score"] = scores

    return part.sort_index()

def hdbscan(df):
    part = df.copy()

    coords = np.radians(part[["lat", "lon"]].to_numpy())

    scan = HDBSCAN(
        min_cluster_size=5,
        metric="haversine"
    )

    labels = scan.fit_predict(coords)

    part["flg"] = labels == -1

    return part.sort_index()

def generate_window_frame(df):
    window = 5
    feature_parts = []
       
    part = df.copy()

    feat_part = build_window_features_for_track(part, window)
    feature_parts.append(feat_part)

    df_window = pd.concat(feature_parts, ignore_index=True)
    df_window = gpd.GeoDataFrame(df_window, geometry="geometry", crs="EPSG:4326")

    window_features = [
        "dist_prev", "dist_next", "dist_skip",
        "dt_prev", "dt_next",
        "speed_prev_mps", "speed_next_mps",
        "center_deviation", "spike_ratio",
        "path_length", "end_to_end", "straightness",
        "mean_seg_dist", "max_seg_dist", "std_seg_dist",
        "mean_speed_mps", "max_speed_mps", "std_speed_mps",
        "mean_acc_mps2", "max_acc_mps2", "std_acc_mps2",
        "mean_angle", "max_angle", "std_angle",
        "speed", "acceleration"
    ]

    return df_window.dropna(subset=window_features).copy()


def make_analysis(df, is_window, algorithm_type):
    # признаки для модели
    base_features = ["x", "y", "speed", "acceleration"]
    window_features = [
        "dist_prev", "dist_next", "dist_skip",
        "dt_prev", "dt_next",
        "speed_prev_mps", "speed_next_mps",
        "center_deviation", "spike_ratio",
        "path_length", "end_to_end", "straightness",
        "mean_seg_dist", "max_seg_dist", "std_seg_dist",
        "mean_speed_mps", "max_speed_mps", "std_speed_mps",
        "mean_acc_mps2", "max_acc_mps2", "std_acc_mps2",
        "mean_angle", "max_angle", "std_angle",
        "speed", "acceleration"
    ]

    if is_window is False:
        match algorithm_type:
            case Algorithm.LOF:
                return lof(df, base_features)
            case Algorithm.ISO:
                return iso(df, base_features)
            case _:
                return hdbscan(df)

    else:
        df_window_model = generate_window_frame(df)

        match algorithm_type:
            case Algorithm.LOF:
                return lof(df_window_model, window_features)
            case Algorithm.ISO:
                return iso(df_window_model, window_features)
            case _:
                return hdbscan(df_window_model)


def parse_args():
    parser = argparse.ArgumentParser(
        description="GPS trajectory outlier detector"
    )

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)

    parser.add_argument(
        "--algorithm",
        choices=["lof", "iso", "hdbscan"],
        default="lof"
    )

    parser.add_argument(
        "--window",
        action="store_true"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    df = prepare_dataframe(args.input)

    result = make_analysis(
        df=df,
        is_window=args.window,
        algorithm_type=Algorithm(args.algorithm)
    )

    columns_to_save = [
        "point_id",
        "traj_id",
        "dt",
        "lat",
        "lon",
        "geometry",
        "flg"
    ]

    if "score" in result.columns:
        columns_to_save.append("score")

    result = result[columns_to_save]

    result.to_pickle(args.output)

    result_geo = result.copy()

    result_geo = gpd.GeoDataFrame(
        result_geo,
        geometry="geometry",
        crs="EPSG:4326"
    )

    geojson_output = args.output.replace(".pkl", ".geojson")

    result_geo.to_file(geojson_output, driver="GeoJSON")

    print(f"PKL saved to: {args.output}")
    print(f"GeoJSON saved to: {geojson_output}")

if __name__ == "__main__":
    try:
        main()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
