#!/usr/bin/env Rscript
################################################################################
# validate_dashboard.R - Validate a generated FoodNetTrends dashboard.html
#
# Usage:
#   Rscript dashboard/test/validate_dashboard.R --dashboard path/to/dashboard.html
#
# Checks:
#   1. File exists and is valid HTML
#   2. Contains window.DASHBOARD_DATA script block
#   3. JSON data block parses without error
#   4. Expected pathogen sections exist
#   5. State view sections exist for all 10 FoodNet states
#   6. Base64 image data or error messages present
#   7. File size within budget (<20MB)
#   8. Cross-link anchors reference valid section IDs
#   9. Prints PASS/FAIL summary
#
# Uses only base R packages (no external dependencies).
################################################################################

# --- Argument parsing (base R only) ---
args <- commandArgs(trailingOnly = TRUE)

dashboard_path <- NULL
for (i in seq_along(args)) {
  if (args[i] == "--dashboard" && i < length(args)) {
    dashboard_path <- args[i + 1]
  }
}

if (is.null(dashboard_path)) {
  cat("Usage: Rscript validate_dashboard.R --dashboard <path/to/dashboard.html>\n")
  quit(status = 1)
}

################################################################################
# Test infrastructure
################################################################################

# Track results
results <- list()
warnings_list <- character(0)

pass <- function(test_name, detail = NULL) {
  msg <- paste0("[PASS] ", test_name)
  if (!is.null(detail)) msg <- paste0(msg, " - ", detail)
  cat(msg, "\n")
  results[[length(results) + 1]] <<- list(name = test_name, status = "PASS", detail = detail)
}

fail <- function(test_name, detail = NULL) {
  msg <- paste0("[FAIL] ", test_name)
  if (!is.null(detail)) msg <- paste0(msg, " - ", detail)
  cat(msg, "\n")
  results[[length(results) + 1]] <<- list(name = test_name, status = "FAIL", detail = detail)
}

warn <- function(test_name, detail = NULL) {
  msg <- paste0("[WARN] ", test_name)
  if (!is.null(detail)) msg <- paste0(msg, " - ", detail)
  cat(msg, "\n")
  warnings_list <<- c(warnings_list, paste0(test_name, ": ", detail))
  results[[length(results) + 1]] <<- list(name = test_name, status = "WARN", detail = detail)
}

################################################################################
# FoodNet configuration
################################################################################

FOODNET_STATES <- c("CA", "CO", "CT", "GA", "MD", "MN", "NM", "NY", "OR", "TN")

STATE_NAMES <- c(
  CA = "California", CO = "Colorado", CT = "Connecticut", GA = "Georgia",
  MD = "Maryland", MN = "Minnesota", NM = "New Mexico", NY = "New York",
  OR = "Oregon", TN = "Tennessee"
)

# Known pathogens in the pipeline
KNOWN_PATHOGENS <- c("CAMPYLOBACTER", "SALMONELLA", "STEC", "SHIGELLA",
                     "VIBRIO", "YERSINIA", "CYCLOSPORA", "LISTERIA",
                     "CRYPTOSPORIDIUM")

cat("========================================\n")
cat("FoodNetTrends Dashboard Validator\n")
cat("========================================\n")
cat("Dashboard:", dashboard_path, "\n\n")

################################################################################
# Test 1: File exists
################################################################################

if (!file.exists(dashboard_path)) {
  fail("File existence", paste("File not found:", dashboard_path))
  cat("\n========================================\n")
  cat("RESULT: FAIL (file not found, cannot continue)\n")
  quit(status = 1)
}
pass("File existence")

################################################################################
# Test 2: File size within budget (<20MB)
################################################################################

file_size <- file.info(dashboard_path)$size
file_size_mb <- file_size / (1024 * 1024)

if (file_size_mb > 20) {
  fail("File size budget", sprintf("%.1f MB exceeds 20 MB limit", file_size_mb))
} else if (file_size_mb > 15) {
  warn("File size budget", sprintf("%.1f MB approaching 20 MB limit", file_size_mb))
} else {
  pass("File size budget", sprintf("%.1f MB", file_size_mb))
}

################################################################################
# Test 3: Valid HTML structure
################################################################################

# Read entire file
html_content <- tryCatch({
  paste(readLines(dashboard_path, warn = FALSE), collapse = "\n")
}, error = function(e) {
  fail("File readable", e$message)
  NULL
})

if (is.null(html_content)) {
  cat("\n========================================\n")
  cat("RESULT: FAIL (cannot read file, cannot continue)\n")
  quit(status = 1)
}

# Check DOCTYPE
if (grepl("<!DOCTYPE\\s+html", html_content, ignore.case = TRUE)) {
  pass("DOCTYPE declaration")
} else {
  fail("DOCTYPE declaration", "Missing <!DOCTYPE html>")
}

# Check html tag
if (grepl("<html[^>]*>", html_content, ignore.case = TRUE) &&
    grepl("</html>", html_content, ignore.case = TRUE)) {
  pass("HTML tag")
} else {
  fail("HTML tag", "Missing <html> or </html> tags")
}

# Check head tag
if (grepl("<head[^>]*>", html_content, ignore.case = TRUE) &&
    grepl("</head>", html_content, ignore.case = TRUE)) {
  pass("HEAD tag")
} else {
  fail("HEAD tag", "Missing <head> or </head> tags")
}

# Check body tag
if (grepl("<body[^>]*>", html_content, ignore.case = TRUE) &&
    grepl("</body>", html_content, ignore.case = TRUE)) {
  pass("BODY tag")
} else {
  fail("BODY tag", "Missing <body> or </body> tags")
}

################################################################################
# Test 4: Contains window.DASHBOARD_DATA script block
################################################################################

has_dashboard_data <- grepl("window\\.DASHBOARD_DATA", html_content)

if (has_dashboard_data) {
  pass("DASHBOARD_DATA script block")
} else {
  fail("DASHBOARD_DATA script block", "window.DASHBOARD_DATA not found in HTML")
}

################################################################################
# Test 5: JSON data block parses without error
################################################################################

json_data <- NULL

if (has_dashboard_data) {
  # Extract JSON from window.DASHBOARD_DATA = {...};
  # Try multiple patterns to be robust
  json_match <- regmatches(html_content,
    regexpr("window\\.DASHBOARD_DATA\\s*=\\s*(\\{[^;]*\\})\\s*;", html_content))

  if (length(json_match) > 0) {
    # Extract just the JSON part
    json_str <- sub("window\\.DASHBOARD_DATA\\s*=\\s*", "", json_match[1])
    json_str <- sub("\\s*;\\s*$", "", json_str)

    # Try to parse using base R's built-in JSON capabilities
    # Since we need base R only, use a simple approach
    # Try writing to a temp file and using a minimal JSON parser

    # First, check if jsonlite is available (it usually is if the dashboard was generated)
    if (requireNamespace("jsonlite", quietly = TRUE)) {
      tryCatch({
        json_data <- jsonlite::fromJSON(json_str, simplifyVector = FALSE)
        pass("JSON parsing", sprintf("Parsed successfully (%d top-level keys)",
                                     length(names(json_data))))
      }, error = function(e) {
        fail("JSON parsing", paste("JSON parse error:", e$message))
      })
    } else {
      # Fallback: basic structural validation without full parse
      # Check balanced braces
      open_braces <- nchar(gsub("[^{]", "", json_str))
      close_braces <- nchar(gsub("[^}]", "", json_str))
      open_brackets <- nchar(gsub("[^\\[]", "", json_str))
      close_brackets <- nchar(gsub("[^\\]]", "", json_str))

      if (open_braces == close_braces && open_brackets == close_brackets) {
        pass("JSON structure (basic)", "Balanced braces/brackets (jsonlite not available for full parse)")
      } else {
        fail("JSON structure (basic)",
             sprintf("Unbalanced: { %d vs } %d, [ %d vs ] %d",
                     open_braces, close_braces, open_brackets, close_brackets))
      }
    }
  } else {
    fail("JSON extraction", "Could not extract JSON from DASHBOARD_DATA block")
  }
}

################################################################################
# Test 6: Expected pathogen sections
################################################################################

# Discover which pathogens are in the data
discovered_pathogens <- character(0)
for (p in KNOWN_PATHOGENS) {
  # Check for pathogen references in the HTML (section IDs, data attributes, etc.)
  pattern <- paste0('id="[^"]*', tolower(p), '[^"]*"')
  if (grepl(pattern, html_content, ignore.case = TRUE) ||
      grepl(paste0('"', p, '"'), html_content) ||
      grepl(paste0("pathogen.*", p), html_content, ignore.case = TRUE)) {
    discovered_pathogens <- c(discovered_pathogens, p)
  }
}

if (length(discovered_pathogens) > 0) {
  pass("Pathogen sections detected",
       paste(length(discovered_pathogens), "pathogens:",
             paste(discovered_pathogens, collapse = ", ")))
} else {
  fail("Pathogen sections detected", "No pathogen sections found in dashboard")
}

# If we parsed JSON, do deeper validation
if (!is.null(json_data)) {
  # Check for pathogen data in the JSON structure
  # The structure depends on the dashboard generator, so be flexible
  pathogens_in_json <- character(0)

  # Try common JSON key patterns
  for (key in c("pathogens", "pathogen_results", "spline_results", "results")) {
    if (key %in% names(json_data)) {
      if (is.list(json_data[[key]])) {
        pathogens_in_json <- names(json_data[[key]])
        break
      }
    }
  }

  # Also search nested structures
  if (length(pathogens_in_json) == 0) {
    # Search all top-level keys for pathogen-like names
    for (key in names(json_data)) {
      for (p in KNOWN_PATHOGENS) {
        if (grepl(p, key, ignore.case = TRUE)) {
          pathogens_in_json <- c(pathogens_in_json, p)
        }
      }
    }
    pathogens_in_json <- unique(pathogens_in_json)
  }

  if (length(pathogens_in_json) > 0) {
    pass("Pathogens in JSON data",
         paste(length(pathogens_in_json), "found:",
               paste(pathogens_in_json, collapse = ", ")))
  } else {
    warn("Pathogens in JSON data",
         "Could not identify pathogen entries in JSON (may use different key structure)")
  }
}

# Check for individual pathogen sections in HTML
for (p in discovered_pathogens) {
  # Look for section content: tables, images, or error messages
  p_lower <- tolower(p)

  has_table_data <- grepl(paste0(p, ".*IRCatch|IRCatch.*", p), html_content, ignore.case = TRUE) ||
                    grepl(paste0(p, ".*ir_catch|ir_catch.*", p), html_content, ignore.case = TRUE) ||
                    grepl(paste0('"', p, '"'), html_content)

  has_error <- grepl(paste0(p, ".*error|error.*", p), html_content, ignore.case = TRUE) ||
               grepl(paste0(p, ".*fail|fail.*", p), html_content, ignore.case = TRUE)

  if (has_table_data || has_error) {
    if (has_error && !has_table_data) {
      pass(paste0("Pathogen section: ", p), "Error/failure indicator present")
    } else {
      pass(paste0("Pathogen section: ", p), "Data content present")
    }
  } else {
    warn(paste0("Pathogen section: ", p), "Referenced but limited content detected")
  }
}

################################################################################
# Test 7: State view sections for all 10 FoodNet states
################################################################################

states_found <- character(0)
states_missing <- character(0)

for (st in FOODNET_STATES) {
  st_name <- STATE_NAMES[st]
  # Check for state section by ID or by state name/abbreviation in context
  has_state_section <- grepl(paste0('id="[^"]*state[_-]?', tolower(st), '[^"]*"'),
                             html_content, ignore.case = TRUE) ||
                       grepl(paste0('id="[^"]*', tolower(st_name), '[^"]*"'),
                             html_content, ignore.case = TRUE) ||
                       grepl(paste0('"state"\\s*:\\s*"', st, '"'),
                             html_content, ignore.case = FALSE)

  # Also check for state abbreviation in headings or navigation
  has_state_ref <- grepl(paste0(">\\s*", st_name, "\\s*<"), html_content, ignore.case = TRUE) ||
                   grepl(paste0(">\\s*", st, "\\s*<"), html_content) ||
                   grepl(paste0('"', st, '"'), html_content)

  if (has_state_section || has_state_ref) {
    states_found <- c(states_found, st)
  } else {
    states_missing <- c(states_missing, st)
  }
}

if (length(states_found) == length(FOODNET_STATES)) {
  pass("State view sections", paste("All", length(FOODNET_STATES), "states present"))
} else if (length(states_found) > 0) {
  warn("State view sections",
       sprintf("%d/%d states found. Missing: %s",
               length(states_found), length(FOODNET_STATES),
               paste(states_missing, collapse = ", ")))
} else {
  fail("State view sections", "No state view sections found")
}

################################################################################
# Test 8: Base64 image data present
################################################################################

# Count Base64-encoded PNG images
b64_png_count <- length(gregexpr("data:image/png;base64,", html_content)[[1]])
if (b64_png_count < 0) b64_png_count <- 0  # gregexpr returns -1 for no match

# Also check for other image formats
b64_img_count <- b64_png_count
b64_jpg_matches <- gregexpr("data:image/jpeg;base64,", html_content)[[1]]
if (b64_jpg_matches[1] > 0) b64_img_count <- b64_img_count + length(b64_jpg_matches)

if (b64_img_count > 0) {
  pass("Base64 image data", sprintf("%d embedded images found", b64_img_count))
} else {
  # Check if there are error messages that explain missing images
  has_error_pathogens <- grepl("(model.*fail|convergence.*error|error\\.txt)",
                               html_content, ignore.case = TRUE)
  if (has_error_pathogens) {
    warn("Base64 image data", "No embedded images, but error indicators present for some pathogens")
  } else {
    fail("Base64 image data", "No embedded images found")
  }
}

################################################################################
# Test 9: Cross-link anchors reference valid section IDs
################################################################################

# Extract all href="#..." anchors
href_matches <- gregexpr('href="#([^"]+)"', html_content)[[1]]
anchor_targets <- character(0)
if (href_matches[1] > 0) {
  for (i in seq_along(href_matches)) {
    start <- href_matches[i]
    len <- attr(href_matches, "match.length")[i]
    href_str <- substr(html_content, start, start + len - 1)
    # Extract the anchor ID
    anchor_id <- sub('href="#([^"]+)"', '\\1', href_str)
    anchor_targets <- c(anchor_targets, anchor_id)
  }
  anchor_targets <- unique(anchor_targets)
}

# Extract all id="..." attributes
id_matches <- gregexpr('id="([^"]+)"', html_content)[[1]]
section_ids <- character(0)
if (id_matches[1] > 0) {
  for (i in seq_along(id_matches)) {
    start <- id_matches[i]
    len <- attr(id_matches, "match.length")[i]
    id_str <- substr(html_content, start, start + len - 1)
    section_id <- sub('id="([^"]+)"', '\\1', id_str)
    section_ids <- c(section_ids, section_id)
  }
  section_ids <- unique(section_ids)
}

# Check that all anchor targets have corresponding IDs
if (length(anchor_targets) > 0) {
  broken_links <- setdiff(anchor_targets, section_ids)
  valid_links <- intersect(anchor_targets, section_ids)

  if (length(broken_links) == 0) {
    pass("Cross-link anchors",
         sprintf("All %d internal links reference valid IDs", length(anchor_targets)))
  } else if (length(broken_links) <= 3) {
    warn("Cross-link anchors",
         sprintf("%d/%d links valid; broken: %s",
                 length(valid_links), length(anchor_targets),
                 paste(broken_links, collapse = ", ")))
  } else {
    fail("Cross-link anchors",
         sprintf("%d/%d links broken (first 5: %s)",
                 length(broken_links), length(anchor_targets),
                 paste(head(broken_links, 5), collapse = ", ")))
  }
} else {
  warn("Cross-link anchors", "No internal anchor links found (may use JS navigation instead)")
}

################################################################################
# Additional checks
################################################################################

# Check for CSS (inline or linked)
if (grepl("<style", html_content, ignore.case = TRUE) ||
    grepl('rel="stylesheet"', html_content, ignore.case = TRUE)) {
  pass("CSS present")
} else {
  warn("CSS present", "No CSS styles found")
}

# Check for JavaScript
if (grepl("<script", html_content, ignore.case = TRUE)) {
  pass("JavaScript present")
} else {
  warn("JavaScript present", "No script tags found")
}

# Check for meta charset
if (grepl('charset', html_content, ignore.case = TRUE)) {
  pass("Character encoding declared")
} else {
  warn("Character encoding declared", "No charset declaration found")
}

################################################################################
# Summary
################################################################################

cat("\n========================================\n")
cat("VALIDATION SUMMARY\n")
cat("========================================\n")

n_pass <- sum(sapply(results, function(r) r$status == "PASS"))
n_fail <- sum(sapply(results, function(r) r$status == "FAIL"))
n_warn <- sum(sapply(results, function(r) r$status == "WARN"))
n_total <- length(results)

cat(sprintf("Total checks: %d\n", n_total))
cat(sprintf("  PASS: %d\n", n_pass))
cat(sprintf("  FAIL: %d\n", n_fail))
cat(sprintf("  WARN: %d\n", n_warn))
cat("\n")

if (n_fail > 0) {
  cat("FAILED CHECKS:\n")
  for (r in results) {
    if (r$status == "FAIL") {
      detail <- if (!is.null(r$detail)) paste0(" - ", r$detail) else ""
      cat(sprintf("  * %s%s\n", r$name, detail))
    }
  }
  cat("\n")
}

if (n_warn > 0) {
  cat("WARNINGS:\n")
  for (r in results) {
    if (r$status == "WARN") {
      detail <- if (!is.null(r$detail)) paste0(" - ", r$detail) else ""
      cat(sprintf("  * %s%s\n", r$name, detail))
    }
  }
  cat("\n")
}

# Overall verdict
cat("========================================\n")
if (n_fail == 0) {
  cat("RESULT: PASS")
  if (n_warn > 0) {
    cat(sprintf(" (with %d warnings)", n_warn))
  }
  cat("\n")
  quit(status = 0)
} else {
  cat(sprintf("RESULT: FAIL (%d failures)\n", n_fail))
  quit(status = 1)
}
