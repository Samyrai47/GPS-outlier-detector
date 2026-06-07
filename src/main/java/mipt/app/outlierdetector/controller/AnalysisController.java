package mipt.app.outlierdetector.controller;

import mipt.app.outlierdetector.service.PythonScriptService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.UUID;

@Controller
@RequestMapping("/analysis")
public class AnalysisController {
    private final PythonScriptService pythonScriptService;

    @Value("${app.analysis.workdir}")
    private String workdir;

    public AnalysisController(PythonScriptService pythonScriptService) {
        this.pythonScriptService = pythonScriptService;
    }

    @GetMapping("/upload")
    public String uploadPage() {
        return "upload";
    }

    @PostMapping("/upload")
    public String analyze(@RequestParam("file") MultipartFile file, @RequestParam(defaultValue = "lof") String algorithm, @RequestParam(defaultValue = "true") boolean window, Model model) throws Exception {
        if (file.isEmpty()) {
            model.addAttribute("error", "Файл не выбран");
            return "upload";
        }

        UUID requestId = UUID.randomUUID();

        Path jobDir = Paths.get(workdir, "sync-" + requestId);
        Files.createDirectories(jobDir);

        Path inputPath = jobDir.resolve("input.pkl");
        Path outputPath = jobDir.resolve("analysis_result.pkl");
        Path stderrPath = jobDir.resolve("stderr.log");
        Path geojsonPath = jobDir.resolve("analysis_result.geojson");

        file.transferTo(inputPath);

        pythonScriptService.runSync(inputPath, outputPath, geojsonPath, stderrPath, jobDir, algorithm, window);

        if (!Files.exists(geojsonPath)) {
            throw new RuntimeException("Python script did not produce GeoJSON file");
        }

        model.addAttribute("message", "Анализ завершен");
        model.addAttribute("requestId", requestId);
        model.addAttribute("pklDownloadUrl", "/analysis/" + requestId + "/result-pkl");
        model.addAttribute("geojsonUrl", "/analysis/" + requestId + "/geojson");

        return "analysis-result";
    }

    @GetMapping("/{requestId}/geojson")
    public ResponseEntity<Resource> getGeoJson(@PathVariable UUID requestId) throws Exception {
        Path geojsonPath = Paths.get(workdir, "sync-" + requestId, "analysis_result.geojson");

        if (!Files.exists(geojsonPath)) {
            return ResponseEntity.notFound().build();
        }

        Resource resource = new UrlResource(geojsonPath.toUri());

        return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(resource);
    }

    @GetMapping("/{requestId}/result-pkl")
    public ResponseEntity<Resource> downloadResultPkl(@PathVariable UUID requestId) throws Exception {
        Path resultPath = Paths.get(workdir, "sync-" + requestId, "analysis_result.pkl");

        if (!Files.exists(resultPath)) {
            return ResponseEntity.notFound().build();
        }

        Resource resource = new UrlResource(resultPath.toUri());

        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM).header("Content-Disposition", "attachment; filename=\"gps_outliers.pkl\"").body(resource);
    }
}
