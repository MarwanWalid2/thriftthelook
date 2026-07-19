export const MAX_SOURCE_IMAGE_BYTES = 25 * 1024 * 1024;
export const TARGET_UPLOAD_BYTES = 3_500_000;

export type PreparedPhoto = {
  photo: File;
  optimized: boolean;
};

export function validateSourceImageSize(size: number): string | null {
  if (size > MAX_SOURCE_IMAGE_BYTES) {
    return "Choose an image smaller than 25 MB.";
  }
  return null;
}

export async function preparePhotoForUpload(file: File): Promise<PreparedPhoto> {
  const sizeError = validateSourceImageSize(file.size);
  if (sizeError) {
    throw new Error(sizeError);
  }
  if (file.size <= TARGET_UPLOAD_BYTES) {
    return { photo: file, optimized: false };
  }

  const source = await loadImage(file);
  try {
    let maxDimension = 2200;
    let quality = 0.88;
    for (let attempt = 0; attempt < 7; attempt += 1) {
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, maxDimension / Math.max(source.width, source.height));
      canvas.width = Math.max(1, Math.round(source.width * scale));
      canvas.height = Math.max(1, Math.round(source.height * scale));
      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error("Your browser could not prepare this image.");
      }
      context.fillStyle = "#fffaf5";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(source.image, 0, 0, canvas.width, canvas.height);
      const blob = await canvasToJpeg(canvas, quality);
      if (blob.size <= TARGET_UPLOAD_BYTES) {
        return {
          photo: new File([blob], jpegName(file.name), { type: "image/jpeg" }),
          optimized: true,
        };
      }
      maxDimension = Math.max(900, Math.round(maxDimension * 0.78));
      quality = Math.max(0.5, quality - 0.07);
    }
  } finally {
    source.close();
  }
  throw new Error("This image could not be optimized for a reliable live search. Try another photo.");
}

type LoadedImage = {
  image: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
};

async function loadImage(file: File): Promise<LoadedImage> {
  if ("createImageBitmap" in window) {
    const bitmap = await createImageBitmap(file);
    return {
      image: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      close: () => bitmap.close(),
    };
  }
  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("This image could not be read."));
      image.src = url;
    });
    return {
      image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      close: () => URL.revokeObjectURL(url),
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

function canvasToJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }
      reject(new Error("This image could not be compressed."));
    }, "image/jpeg", quality);
  });
}

function jpegName(name: string): string {
  const stem = name.replace(/\.[^.]+$/, "").slice(0, 90) || "outfit";
  return `${stem}-optimized.jpg`;
}
