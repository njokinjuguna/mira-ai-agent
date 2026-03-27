import { useState } from "react";
import NextImage from "next/image";

interface ImageData {
  image_url: string; // "/image/<id>" OR "/generated/<file>.png"
  caption: string;
  score?: number;
}

interface ImageWithLoaderProps {
  img: ImageData;
}

export default function ImageWithLoader({ img }: ImageWithLoaderProps) {
  const [loaded, setLoaded] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [showModal, setShowModal] = useState(false);

  const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

  /**
   * ✅ IMPORTANT:
   * - If image_url already starts with "/image/" → keep it
   * - If it starts with "/generated/" → keep it
   * - If full http URL → keep it
   * - Otherwise fallback to "/image/<id>"
   */
  let backendImageUrl = img.image_url;

  if (backendImageUrl.startsWith("http://") || backendImageUrl.startsWith("https://")) {
    // use as is
  } else if (backendImageUrl.startsWith("/image/")) {
    backendImageUrl = `${API_BASE}${backendImageUrl}`;
  } else if (backendImageUrl.startsWith("/generated/")) {
    backendImageUrl = `${API_BASE}${backendImageUrl}`;
  } else {
    backendImageUrl = `${API_BASE}/image/${backendImageUrl}`;
  }

  function openModal() {
    setRotation(0);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setRotation(0);
  }

  return (
    <>
      {/* Thumbnail */}
      <div
        className="bg-white border rounded-xl p-2 shadow-sm w-full overflow-visible cursor-pointer"
        onClick={openModal}
      >
        <div className="relative bg-gray-100 flex items-center justify-center overflow-hidden rounded-md">
          {!loaded && <div className="absolute w-full h-full bg-gray-200 animate-pulse" />}

          <NextImage
            src={backendImageUrl}
            alt={img.caption}
            width={400}
            height={300}
            className="rounded w-full max-h-[300px] object-cover"
            unoptimized
            onLoad={() => setLoaded(true)}
          />
        </div>

        <div className="mt-2 text-xs text-gray-600">
          <span className="truncate block">{img.caption}</span>
        </div>
      </div>

      {/* Modal Viewer */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 bg-black bg-opacity-80 flex items-center justify-center"
          onClick={closeModal}
        >
          <div
            className="relative max-h-[90vh] max-w-[90vw] overflow-auto bg-black rounded-lg p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="relative transform transition-transform duration-300 mx-auto"
              style={{ transform: `rotate(${rotation}deg)` }}
            >
              <NextImage
                src={backendImageUrl}
                alt={img.caption}
                width={900}
                height={675}
                className="rounded-xl object-contain max-w-[80vw] max-h-[80vh]"
                unoptimized
              />
            </div>

            <button
              className="absolute top-4 right-4 bg-white text-black px-3 py-1 rounded-full"
              onClick={closeModal}
            >
              ✕ Close
            </button>

            <button
              onClick={() => setRotation((r) => (r + 90) % 360)}
              className="absolute bottom-6 right-6 bg-white text-xs px-3 py-1 rounded"
            >
              ↻ Rotate
            </button>
          </div>
        </div>
      )}
    </>
  );
}
