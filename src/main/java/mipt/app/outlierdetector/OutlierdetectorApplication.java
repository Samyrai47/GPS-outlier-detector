package mipt.app.outlierdetector;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class OutlierdetectorApplication {
  public static void main(String[] args) {
    SpringApplication.run(OutlierdetectorApplication.class, args);
  }
}
