import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_SOURCE_IMAGE_BYTES,
  validateSourceImageSize,
} from "../app/image-upload.ts";

test("accepts an image at the 25 MB source limit", () => {
  assert.equal(validateSourceImageSize(MAX_SOURCE_IMAGE_BYTES), null);
});

test("rejects an image larger than the 25 MB source limit", () => {
  assert.match(
    validateSourceImageSize(MAX_SOURCE_IMAGE_BYTES + 1) ?? "",
    /25 MB/,
  );
});
