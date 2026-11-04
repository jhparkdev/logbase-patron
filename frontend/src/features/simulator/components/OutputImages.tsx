import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type { SlotView } from "../lib/presentation";

/** 이미지 출력 칸의 결과. 파일은 서버를 거쳐 받으므로 주소만 그린다. */
export function OutputImages({
  name,
  images,
  ongoing,
}: {
  name: string;
  images: NonNullable<SlotView["images"]>;
  ongoing: boolean;
}) {
  if (!images.length && ongoing)
    return (
      <div className="rounded-lg bg-grey-50 p-3.5">
        <p className="sr-only">이미지를 기다리고 있어요</p>
        <Skeleton className="aspect-square w-full" />
      </div>
    );
  if (!images.length)
    return (
      <p className="rounded-lg bg-grey-50 p-3 text-body-sm text-grey-700">
        받은 이미지가 없어요.
      </p>
    );
  return (
    <ul className="grid grid-cols-2 gap-2">
      {images.map((image, index) => (
        <li key={image.key} className={images.length === 1 ? "col-span-2" : ""}>
          <a href={image.url} target="_blank" rel="noreferrer">
            <img
              src={image.url}
              alt={`${name} 결과 이미지 ${index + 1}`}
              loading="lazy"
              className="w-full rounded-lg bg-grey-50 object-contain"
            />
          </a>
        </li>
      ))}
    </ul>
  );
}
