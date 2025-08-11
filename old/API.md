# Mokuro API Server – API Documentation

A complete, implementation‑accurate description of the Mokuro API Server as observed from the codebase and validated against a running instance at `http://localhost:7331`. This document is intended for faithful re‑implementation in a new project.

- Base URL: `http://localhost:7331`
- Auth: none
- CORS: enabled (`Access-Control-Allow-Origin: *`)
- Max upload size: 50MB (request body)
- Supported image types: `png, jpg, jpeg, webp, avif, bmp, tiff`
- Content type: `application/json` for all responses
- Version: `0.2.2` (returned in `/health`, `/api/info`, and OCR results)

Notes
- Endpoints accept `multipart/form-data` for image uploads.
- OCR engines are discovered at runtime via a registry and are kept in memory (warm) for performance.
- Temporary files are used for processing and cleaned up after each request.
- Errors return JSON with an `error` string and a relevant HTTP status code.


## Health

GET `/health`

Returns server status, Mokuro version, and currently available OCR engines.

Example response (observed):
```json
{
  "available_engines": ["lens", "manga-ocr"],
  "status": "healthy",
  "version": "0.2.2"
}
```


## API Info

GET `/api/info`

Describes API capabilities, supported formats, size limits, and engine availability at runtime.

Example response (abridged, observed):
```json
{
  "name": "Mokuro API Server",
  "version": "0.2.2",
  "supported_formats": ["avif","jpg","tiff","webp","png","bmp","jpeg"],
  "max_file_size": "50MB",
  "endpoints": {
    "/api/ocr": {
      "method": "POST",
      "description": "Process a single image",
      "parameters": {
        "image": "Image file (required)",
        "ocr_engine": "manga-ocr or lens (optional, default: manga-ocr)",
        "force_cpu": "boolean (optional, default: false)"
      }
    },
    "/api/ocr/batch": {
      "method": "POST",
      "description": "Process multiple images",
      "parameters": {
        "images": "Multiple image files (required)",
        "ocr_engine": "manga-ocr or lens (optional, default: manga-ocr)",
        "force_cpu": "boolean (optional, default: false)"
      }
    }
  },
  "ocr_engines": {
    "lens": "Google Lens OCR with multilingual support (requires Node.js and chrome-lens-ocr)",
    "manga-ocr": "Fast offline OCR specialized for Japanese manga"
  },
  "ocr_engines_detailed": {
    "lens": {
      "available": true,
      "requirements": [
        "Node.js",
        "chrome-lens-ocr npm package (install with: npm install chrome-lens-ocr)",
        "lens_ocr_wrapper.js in project root"
      ],
      "suggested_language_code": "gl"
    },
    "manga-ocr": {
      "available": true,
      "requirements": [
        "manga-ocr Python package",
        "PyTorch",
        "Transformers library"
      ],
      "suggested_language_code": "mo"
    }
  }
}
```


## Process One Image

POST `/api/ocr`

Multipart form-data parameters:
- `image` (required): The image file to process.
- `ocr_engine` (optional): Which OCR engine to use. Must be one of the values reported by `/health` or `/api/info`. Defaults to `manga-ocr`.
- `force_cpu` (optional): String boolean. Only the literal `"true"` (any case) is treated as true; all other values are false. Default is false.

Behavior:
- Validates presence of `image` and that its extension is one of the supported formats.
- Validates `ocr_engine` is currently available; otherwise responds with 400.
- Saves the uploaded file to a temp file, processes it, then deletes it.
- Returns an OCR result JSON object (see Data Model) with `filename` and `ocr_engine` fields added.

Example: default engine (`manga-ocr`)
```bash
curl -X POST http://localhost:7331/api/ocr \
  -F "image=@tests/data/input/test0/vol1/000a.jpg"
```
Response (abridged):
```json
{
  "version": "0.2.2",
  "filename": "000a.jpg",
  "ocr_engine": "manga-ocr",
  "img_width": 827,
  "img_height": 1170,
  "blocks": [
    {
      "box": [37,0,863,235],
      "vertical": null,
      "font_size": 137.5,
      "lines_coords": [
        [[582.0,18.0],[785.0,13.0],[787.0,53.0],[583.0,58.0]],
        [[37.0,0.0],[863.0,0.0],[863.0,235.0],[37.0,235.0]]
      ],
      "lines": ["ダイアリー・","うちの猫ず日記"]
    },
    { "box": [233,1048,608,1170], ... }
  ]
}
```

Example: select Google Lens engine
```bash
curl -X POST http://localhost:7331/api/ocr \
  -F "image=@tests/data/input/test0/vol1/000a.jpg" \
  -F "ocr_engine=lens"
```
Response (abridged; text content differs between engines):
```json
{
  "version": "0.2.2",
  "filename": "000a.jpg",
  "ocr_engine": "lens",
  "img_width": 827,
  "img_height": 1170,
  "blocks": [
    {
      "box": [37,0,863,235],
      "font_size": 137.5,
      "lines": ["ダイアリー","にゃん タイアリーうちの猫ず日記"],
      "lines_coords": [...],
      "vertical": null
    },
    ...
  ]
}
```

Example: force CPU
```bash
curl -X POST http://localhost:7331/api/ocr \
  -F "image=@tests/data/input/test0/vol1/002a.jpg" \
  -F "force_cpu=true"
```
Example response (counts only):
```json
{"ocr_engine":"manga-ocr","img_width":827,"img_height":1170,"blocks_count":17}
```

Error examples (observed):
- Missing file
  - Request: `POST /api/ocr` with no form data
  - Response: `400`
    ```json
    {"error":"No image file provided"}
    ```
- Invalid file type
  - Request: `-F "image=@README.md"`
  - Response: `400`
    ```json
    {"error":"Invalid file type. Allowed types: avif, jpg, tiff, webp, png, bmp, jpeg"}
    ```
  - Note: the order of extensions in the message reflects iteration order of the server’s allowed set.
- Invalid OCR engine
  - Request: `-F "image=@.../000a.jpg" -F "ocr_engine=notreal"`
  - Response: `400`
    ```json
    {"error":"Invalid OCR engine. Available engines: lens, manga-ocr"}
    ```
- Payload too large (> 50MB)
  - Response: `413`
    ```json
    {"error":"File too large. Maximum size is 50MB"}
    ```
- Internal error
  - Response: `500`
    ```json
    {"error":"Internal server error"}
    ```


## Process Multiple Images (Batch)

POST `/api/ocr/batch`

Multipart form-data parameters:
- `images` (required): Repeat this field for each file.
- `ocr_engine` (optional): Same rules as single-image endpoint.
- `force_cpu` (optional): Same rules as single-image endpoint.

Behavior:
- Validates that at least one `images` file part is provided; otherwise 400.
- For each provided file:
  - If extension invalid, appends an error object for that file (request still returns 200).
  - Otherwise processes the file with the selected engine and appends the OCR result object.
- Response is always 200 unless the entire request is malformed or an unhandled exception occurs. Individual item errors are embedded in `results`.

Example:
```bash
curl -X POST http://localhost:7331/api/ocr/batch \
  -F "images=@tests/data/input/test0/vol1/000a.jpg" \
  -F "images=@tests/data/input/test0/vol1/001a.jpg"
```
Response (counts):
```json
{
  "results": [
    {"filename":"000a.jpg","img_width":827,"img_height":1170,"blocks":[...]},
    {"filename":"001a.jpg","img_width":827,"img_height":1170,"blocks":[...]}
  ]
}
```

Mixed valid + invalid file:
```bash
curl -X POST http://localhost:7331/api/ocr/batch \
  -F "images=@tests/data/input/test0/vol1/000a.jpg" \
  -F "images=@README.md"
```
Response:
```json
{
  "results": [
    {"filename":"000a.jpg","version":"0.2.2","ocr_engine":"manga-ocr", ...},
    {"filename":"README.md","error":"Invalid file type. Allowed types: avif, jpg, tiff, webp, png, bmp, jpeg"}
  ]
}
```

Error example:
- Missing files
  - Request: `POST /api/ocr/batch` with no form data
  - Response: `400`
    ```json
    {"error":"No image files provided"}
    ```


## Data Model

OCR result object (per image):
- `version` (string): Mokuro library version that produced the result (e.g., `"0.2.2"`).
- `img_width` (number): Image width in pixels.
- `img_height` (number): Image height in pixels.
- `blocks` (array of Block): Detected text blocks.

Block:
- `box` (array[number, number, number, number]): Bounding rectangle `[x0, y0, x1, y1]`.
- `vertical` (boolean|null): Whether block text is vertical. May be `null` if not applicable.
- `font_size` (number): Estimated font size.
- `lines_coords` (array of 4-point polygons): For each recognized line, a 4‑point quadrilateral `[[x,y], [x,y], [x,y], [x,y]]`.
- `lines` (array[string]): Recognized line texts (same order as `lines_coords`).

Fields added by API:
- `filename` (string): Original uploaded filename.
- `ocr_engine` (string): Engine used for OCR (e.g., `"manga-ocr"`, `"lens"`).

Batch responses:
- Top-level: `{ "results": [ ... ] }` where each element is either:
  - an OCR result object (as above), or
  - an error object: `{ "filename": string, "error": string }`.


## Parameters and Validation

- `image` (single upload): required for `/api/ocr`.
- `images` (batch upload): required for `/api/ocr/batch` (at least one part).
- Allowed extensions: `{png, jpg, jpeg, webp, avif, bmp, tiff}` (extension is checked case‑insensitively).
- `ocr_engine`: default `"manga-ocr"`; must be listed in `available_engines`.
- `force_cpu`: only the literal string `"true"` (case‑insensitive) becomes `True`; anything else is `False`.
- File size: requests exceeding `50MB` return `413` with a JSON error.


## Error Handling

- `200 OK`:
  - Successful single image processing.
  - Batch processing even with some invalid items (per‑item errors embedded in `results`).
- `400 Bad Request`:
  - Missing required file part(s).
  - Invalid file type.
  - Invalid OCR engine.
- `413 Request Entity Too Large`:
  - Request exceeds configured max size.
- `500 Internal Server Error`:
  - Unhandled exceptions produce `{ "error": "Internal server error" }`.
  - Handler‑level exceptions during processing may respond `{ "error": "Processing failed: ..." }` or `{ "error": "Batch processing failed: ..." }` with status 500.


## Engines and Behavior

- Engines are registered dynamically via an OCR registry and may vary by environment.
- To discover engines at runtime, use `/health` or `/api/info`.
- Common engines:
  - `manga-ocr`: local, fast, specialized for Japanese manga; supports GPU (CUDA/MPS) if available unless `force_cpu=true`.
  - `lens`: uses a Node.js wrapper (chrome‑lens‑ocr) around Google Lens OCR; requires Node.js and a wrapper script; has internal retry/backoff and a small delay between attempts.
- The detection/OCR pipeline:
  1. Detect text regions with a CNN-based text detector.
  2. Segment into blocks and lines; rotate vertical lines as needed and split very long lines into chunks.
  3. Run the chosen OCR engine per line/chunk.
  4. Return block rectangles (`box`), line polygons (`lines_coords`), and recognized text (`lines`).
- Batch requests reuse a single engine instance for all images in that request.


## Environment and Runtime

- Host/Port defaults:
  - Host: `0.0.0.0`
  - Port: `7331`
- Environment variables (server runtime):
  - `MOKURO_HOST` (default `0.0.0.0`)
  - `MOKURO_PORT` (default `7331`)
  - `MOKURO_DEBUG` (`true`/`false`, default `false`)
  - `MOKURO_PRELOAD_MODELS` (`true`/`false`, default `true`): preloads available engines at startup
- CORS: enabled globally.
- JSON: numpy ints/floats/arrays are serialized to plain JSON numbers/arrays; clients see normal JSON types.


## End-to-End Examples

- WebP support
```bash
curl -X POST http://localhost:7331/api/ocr \
  -F "image=@tests/data/input/test1_webp/vol1/000a.webp"
```
Response (counts):
```json
{"filename":"000a.webp","img_width":827,"img_height":1170,"blocks_count":2}
```

- Minimal batch with two images
```bash
curl -X POST http://localhost:7331/api/ocr/batch \
  -F "images=@tests/data/input/test0/vol1/000a.jpg" \
  -F "images=@tests/data/input/test0/vol1/001a.jpg"
```
Response (counts):
```json
{
  "results_count": 2,
  "sample0": {"filename":"000a.jpg","img_width":827,"img_height":1170,"blocks":2},
  "sample1": {"filename":"001a.jpg","img_width":827,"img_height":1170,"blocks":13}
}
```


## OpenAPI 3.0 Schema (YAML)

```yaml
openapi: 3.0.3
info:
  title: Mokuro API Server
  version: "0.2.2"
servers:
  - url: http://localhost:7331
paths:
  /health:
    get:
      summary: Health check
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [status, version, available_engines]
                properties:
                  status:
                    type: string
                    example: healthy
                  version:
                    type: string
                    example: "0.2.2"
                  available_engines:
                    type: array
                    items:
                      type: string
                    example: ["lens","manga-ocr"]
  /api/info:
    get:
      summary: API capabilities
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [name, version, supported_formats, max_file_size, endpoints, ocr_engines, ocr_engines_detailed]
                properties:
                  name: { type: string }
                  version: { type: string }
                  supported_formats:
                    type: array
                    items: { type: string }
                  max_file_size: { type: string, example: "50MB" }
                  endpoints:
                    type: object
                    additionalProperties: { type: object }
                  ocr_engines:
                    type: object
                    additionalProperties: { type: string }
                  ocr_engines_detailed:
                    type: object
                    additionalProperties:
                      type: object
                      properties:
                        available: { type: boolean }
                        description: { type: string }
                        requirements:
                          type: array
                          items: { type: string }
                        suggested_language_code: { type: string }
  /api/ocr:
    post:
      summary: Process a single image
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [image]
              properties:
                image:
                  type: string
                  format: binary
                  description: Image file (png, jpg, jpeg, webp, avif, bmp, tiff)
                ocr_engine:
                  type: string
                  description: OCR engine to use (defaults to manga-ocr)
                force_cpu:
                  type: string
                  description: "Boolean string: 'true'/'false' (default false)"
      responses:
        "200":
          description: OCR result
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/OcrResultWithMeta"
        "400":
          description: Bad request
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "413":
          description: Payload too large
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "500":
          description: Internal error
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
  /api/ocr/batch:
    post:
      summary: Process multiple images
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [images]
              properties:
                images:
                  type: array
                  items:
                    type: string
                    format: binary
                  description: Repeat the 'images' field for each file
                ocr_engine:
                  type: string
                force_cpu:
                  type: string
      responses:
        "200":
          description: Batch results with per-item success or error
          content:
            application/json:
              schema:
                type: object
                required: [results]
                properties:
                  results:
                    type: array
                    items:
                      oneOf:
                        - $ref: "#/components/schemas/OcrResultWithMeta"
                        - $ref: "#/components/schemas/ErrorWithFilename"
        "400":
          description: Bad request
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "413":
          description: Payload too large
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "500":
          description: Internal error
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
components:
  schemas:
    OcrResult:
      type: object
      required: [version, img_width, img_height, blocks]
      properties:
        version:
          type: string
          example: "0.2.2"
        img_width:
          type: number
          format: float
          example: 827
        img_height:
          type: number
          format: float
          example: 1170
        blocks:
          type: array
          items:
            $ref: "#/components/schemas/Block"
    OcrResultWithMeta:
      allOf:
        - $ref: "#/components/schemas/OcrResult"
        - type: object
          properties:
            filename:
              type: string
              example: "000a.jpg"
            ocr_engine:
              type: string
              example: "manga-ocr"
    Block:
      type: object
      required: [box, font_size, lines_coords, lines]
      properties:
        box:
          type: array
          items: { type: number }
          minItems: 4
          maxItems: 4
          example: [37, 0, 863, 235]
        vertical:
          type: boolean
          nullable: true
        font_size:
          type: number
          format: float
          example: 137.5
        lines_coords:
          type: array
          items:
            type: array
            items:
              type: array
              items: { type: number }
              minItems: 2
              maxItems: 2
            minItems: 4
            maxItems: 4
          example: [[[582.0,18.0],[785.0,13.0],[787.0,53.0],[583.0,58.0]]]
        lines:
          type: array
          items: { type: string }
          example: ["ダイアリー・","うちの猫ず日記"]
    Error:
      type: object
      required: [error]
      properties:
        error:
          type: string
    ErrorWithFilename:
      allOf:
        - $ref: "#/components/schemas/Error"
        - type: object
          required: [filename]
          properties:
            filename:
              type: string
```


## Re‑implementation Checklist

- Server Basics
  - CORS enabled for all origins.
  - Default host/port: `0.0.0.0:7331`.
  - Env vars: `MOKURO_HOST`, `MOKURO_PORT`, `MOKURO_DEBUG`, `MOKURO_PRELOAD_MODELS`.
  - Max body size: 50MB → return 413 with `{ "error": "File too large. Maximum size is 50MB" }`.
  - Save uploads to temp dir; name with UUID + sanitized filename; delete in finally.

- Endpoints
  - GET `/health` → `{ status, version, available_engines }`.
  - GET `/api/info` → capabilities, formats, limits, short and detailed engines.
  - POST `/api/ocr` → multipart with `image` (required), `ocr_engine` (optional), `force_cpu` (optional).
  - POST `/api/ocr/batch` → multipart with repeated `images` (required), optional `ocr_engine`, `force_cpu`.

- Request Parsing
  - `ocr_engine` default `manga-ocr`; must be in runtime available list.
  - `force_cpu`: only string `"true"` → true; otherwise false.

- Validation
  - Allowed extensions: `png, jpg, jpeg, webp, avif, bmp, tiff`.
  - `/api/ocr` errors:
    - 400 no image: `{ "error": "No image file provided" }`.
    - 400 bad type: `{ "error": "Invalid file type. Allowed types: ..." }` (order of types may vary).
    - 400 bad engine: `{ "error": "Invalid OCR engine. Available engines: <list>" }`.
  - `/api/ocr/batch` errors:
    - 400 no images: `{ "error": "No image files provided" }`.
    - Mixed input: per-item errors in `results`; overall 200.

- OCR Engine Registry & Caching
  - Registry with `register`, `list_engines`, `get_available_engines`, `get_engine_instance`.
  - Cache key:
    - `manga-ocr`: depends on `force_cpu` only (e.g., `manga-ocr:force_cpu=true|false`).
    - Others: include full kwargs.
  - Engines:
    - `manga-ocr` (local, GPU/MPS if available unless forced CPU).
    - `lens` (Node.js + chrome‑lens‑ocr; wrapper script; limited retries + small delay inside engine).

- Detection + OCR Pipeline
  - Detect text regions, segment blocks/lines, rotate vertical lines, split long lines.
  - OCR each line/chunk; assemble `lines` and `lines_coords`.

- Response Shape
  - Per-image result fields: `version`, `img_width`, `img_height`, `blocks`.
  - Block fields: `box`, `vertical`, `font_size`, `lines_coords` (4‑point polygons per line), `lines`.
  - API adds: `filename`, `ocr_engine`.
  - Batch: `{ "results": [ OcrResult | { filename, error } ] }`.

- Status Codes
  - 200 on success; 200 for batch with per-item errors.
  - 400 for missing file(s)/invalid engine/invalid type.
  - 413 for too large.
  - 500 for unhandled/internal processing errors.

- Serialization & Headers
  - JSON only; ensure numpy‑like types serialize to plain JSON numbers/arrays.
  - CORS header `Access-Control-Allow-Origin: *` on all responses.

- Startup (optional)
  - If preloading enabled, load each available engine at startup and cache instance.

- Tests (parity checks)
  - Verify all examples and error messages above.
  - Confirm `/api/info` keys and structure.
  - Confirm batch mixed success/error behavior (HTTP 200, per-item error objects).

