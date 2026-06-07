package mipt.app.outlierdetector.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class PageController {
  @GetMapping({"/", "/upload"})
  public String uploadPage() {
    return "upload";
  }
}
