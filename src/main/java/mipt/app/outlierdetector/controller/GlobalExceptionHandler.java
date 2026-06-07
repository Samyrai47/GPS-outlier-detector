package mipt.app.outlierdetector.controller;

import jakarta.servlet.http.HttpServletResponse;
import mipt.app.outlierdetector.dto.ErrorResponse;
import mipt.app.outlierdetector.exception.InvalidFileException;
import mipt.app.outlierdetector.exception.PythonScriptException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.ui.Model;

@ControllerAdvice
public class GlobalExceptionHandler {
  @ExceptionHandler(InvalidFileException.class)
  public String handleUserNotFound(
      InvalidFileException exception, Model model, HttpServletResponse response) {
    response.setStatus(HttpStatus.BAD_REQUEST.value());

    model.addAttribute("status", 400);
    model.addAttribute("error", "Bad Request");
    model.addAttribute("message", exception.getMessage());

    return "error-page";
  }

  @ExceptionHandler(PythonScriptException.class)
  public String handlePythonScriptException(
      PythonScriptException exception, Model model, HttpServletResponse response) {
    response.setStatus(HttpStatus.INTERNAL_SERVER_ERROR.value());

    model.addAttribute("status", 500);
    model.addAttribute("error", "Internal Server Error");
    model.addAttribute("message", exception.getMessage());

    return "error-page";
  }
}
