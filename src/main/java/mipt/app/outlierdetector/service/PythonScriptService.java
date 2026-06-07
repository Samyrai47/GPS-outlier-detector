package mipt.app.outlierdetector.service;

import mipt.app.outlierdetector.exception.InvalidFileException;
import mipt.app.outlierdetector.exception.PythonScriptException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Service
public class PythonScriptService {
  @Value("${app.python.executable}")
  private String pythonExecutable;

  @Value("${app.python.script-path}")
  private String scriptPath;

  public Path runSync(
      Path inputPath,
      Path outputPath,
      Path geojsonPath,
      Path stderrPath,
      Path jobDir,
      String algorithm,
      boolean window)
      throws Exception {
    List<String> command = new ArrayList<>();

    command.add(pythonExecutable);
    command.add(scriptPath);

    command.add("--input");
    command.add(inputPath.toString());

    command.add("--output");
    command.add(outputPath.toString());

    command.add("--algorithm");
    command.add(algorithm);

    if (window) {
      command.add("--window");
    }

    Path stdoutPath = jobDir.resolve("stdout.log");

    ProcessBuilder pb = new ProcessBuilder(command);

    pb.directory(jobDir.toFile());
    pb.redirectError(stderrPath.toFile());
    pb.redirectOutput(stdoutPath.toFile());

    Process process = pb.start();

    boolean finished = process.waitFor(2, TimeUnit.MINUTES);

    if (!finished) {
      process.destroyForcibly();
      throw new RuntimeException("Python script timeout");
    }

    int exitCode = process.exitValue();

    if (exitCode != 0) {
      String stderr = Files.exists(stderrPath) ? Files.readString(stderrPath).trim() : "";

      if (exitCode == 2) {
        throw new InvalidFileException(extractLastNonEmptyLine(stderr));
      }

      throw new PythonScriptException(
          "Python script failed with code " + exitCode + ":\n" + stderr);
    }

    if (!Files.exists(outputPath)) {
      throw new PythonScriptException("Python script did not produce PKL file: " + outputPath);
    }

    if (!Files.exists(geojsonPath)) {
      throw new PythonScriptException("Python script did not produce GeoJSON file: " + geojsonPath);
    }

    return outputPath;
  }

  private String extractLastNonEmptyLine(String text) {
    if (text == null || text.isBlank()) {
      return "";
    }

    String[] lines = text.split("\\R");

    for (int i = lines.length - 1; i >= 0; i--) {
      String line = lines[i].trim();

      if (!line.isEmpty()) {
        return line;
      }
    }

    return "";
  }
}
