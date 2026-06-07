package mipt.app.outlierdetector.dto;

public record ErrorResponse(int status, String error, String message) {
}
