package mipt.app.outlierdetector.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.Duration;
import java.time.Instant;

@Service
public class AnalysisCleanupService {

  @Value("${app.analysis.workdir}")
  private String workdir;

  @Value("${app.analysis.ttl-minutes:20}")
  private long ttlMinutes;

  @Scheduled(fixedDelay = 10 * 60 * 1000)
  public void cleanupOldAnalysisResults() throws IOException {
    Path root = Paths.get(workdir);

    if (!Files.exists(root)) {
      return;
    }

    Instant now = Instant.now();
    Duration ttl = Duration.ofMinutes(ttlMinutes);

    try (DirectoryStream<Path> stream = Files.newDirectoryStream(root, "sync-*")) {
      for (Path jobDir : stream) {
        if (!Files.isDirectory(jobDir)) {
          continue;
        }

        BasicFileAttributes attrs = Files.readAttributes(jobDir, BasicFileAttributes.class);
        Instant createdAt = attrs.creationTime().toInstant();

        if (Duration.between(createdAt, now).compareTo(ttl) > 0) {
          deleteDirectory(jobDir);
        }
      }
    }
  }

  private void deleteDirectory(Path directory) throws IOException {
    Files.walkFileTree(
        directory,
        new SimpleFileVisitor<>() {

          @Override
          public FileVisitResult visitFile(Path file, BasicFileAttributes attrs)
              throws IOException {
            Files.deleteIfExists(file);
            return FileVisitResult.CONTINUE;
          }

          @Override
          public FileVisitResult postVisitDirectory(Path dir, IOException exception)
              throws IOException {
            Files.deleteIfExists(dir);
            return FileVisitResult.CONTINUE;
          }
        });
  }
}
