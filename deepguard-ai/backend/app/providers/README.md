# providers/

External API clients that the app calls for additional analysis. The main provider is
Sightengine, a commercial deepfake-detection API that gives a second opinion alongside
the LLM reasoning.

## Files

- **sightengine.py** — REST client for the Sightengine API. Sends images or videos,
  parses response v3, handles image resizing for large files, and runs 5-frame parallel
  analysis on videos with worst-first aggregation.

## Walkthroughs

### sightengine.py

1. Image is uploaded and passed to the Sightengine client
2. Check if the longest side of the image is > 2048 pixels
3. If yes, resize the image with LANCZOS downsampling to fit within 2048px
4. POST the image (or each of the 5 video key frames) to the Sightengine API
5. Parse the JSON response using the v3 response parser
6. Extract deepfake probability and gen-AI probability from the parsed response
7. Normalize probabilities into a verdict: `real` if both probabilities < 0.25,
   `fake` if either > 0.75, otherwise `inconclusive`
8. Return a verdict JSON object with confidence field
