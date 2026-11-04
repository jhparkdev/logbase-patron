import { useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import { SearchField } from "../../../shared/components/ui/SearchField";
import { selectedComparisonCount } from "../lib/comparisons";
import {
  emptyCatalogMessage,
  type ModelFavoritesView,
  searchFavoriteModels,
  unavailableFavorites,
} from "../lib/favorites";
import { MODEL_LIMITS } from "../lib/limits";
import { canApplyModels, selectedModelKeys } from "../lib/model-selection";
import type { ModelChoice } from "../lib/presentation";
import { ModelCatalogTable } from "./ModelCatalogTable";
import { ModelCreatorBadge } from "./ModelCreatorBadge";
import { ModelFavoritesNotice } from "./ModelFavoritesNotice";

const SEGMENT_CLASS =
  "h-8 rounded-lg px-3 text-label font-semibold text-grey-600 aria-pressed:bg-white aria-pressed:text-grey-900 aria-pressed:shadow-sm focus-visible:outline-2 focus-visible:outline-brand";

export function ModelPickerDialog({
  choices,
  selections,
  counts = {},
  unavailable,
  favorites = unavailableFavorites,
  imagesAttached = false,
  onClose,
  onApply,
}: {
  choices: ModelChoice[];
  selections: string[];
  counts?: Readonly<Record<string, number>>;
  unavailable: boolean;
  favorites?: ModelFavoritesView;
  /** 이미지를 첨부한 상태면 이미지 지원 모델만 보는 필터를 제안한다 */
  imagesAttached?: boolean;
  onClose: () => void;
  onApply: (keys: string[]) => void;
}) {
  const [pending, setPending] = useState(() => selectedModelKeys(selections));
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [imagesOnly, setImagesOnly] = useState(false);
  const matches = searchFavoriteModels(
    choices,
    query,
    favoritesOnly,
    favorites,
  ).filter((choice) => !imagesOnly || choice.supportsImages);
  const empty = emptyCatalogMessage(query, favoritesOnly, favorites);
  const count = selectedComparisonCount(pending, counts);
  const remaining = MODEL_LIMITS.max - count;
  const canApply = !unavailable && canApplyModels(pending, choices, counts);
  const remove = (key: string) =>
    setPending((keys) => keys.filter((value) => value !== key));
  const toggle = (key: string) =>
    setPending((keys) => {
      if (keys.includes(key)) return keys.filter((value) => value !== key);
      if (
        unavailable ||
        selectedComparisonCount([...keys, key], counts) > MODEL_LIMITS.max ||
        !choices.some((choice) => choice.key === key && choice.selectable)
      )
        return keys;
      return [...keys, key];
    });

  // 검색 입력의 Enter가 바깥 실행 폼을 제출하지 않도록 폼 밖에 띄운다.
  return createPortal(
    <Dialog
      open
      title="비교 모델 선택"
      onClose={onClose}
      showTopClose
      action={
        <Button
          disabled={!canApply}
          onClick={() => {
            if (canApply) onApply(pending);
          }}
        >
          선택 적용
        </Button>
      }
    >
      <p className="text-caption text-grey-600">
        {MODEL_LIMITS.min}~{MODEL_LIMITS.max}개를 고르면 실행할 수 있어요. 같은
        모델을 다른 설정으로 비교하려면 적용한 뒤 카드에서 ‘복제’해요.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <fieldset
          aria-label="모델 목록 범위"
          className="flex rounded-xl bg-grey-100 p-1"
        >
          <button
            type="button"
            aria-label="전체 모델 목록"
            aria-pressed={!favoritesOnly}
            className={SEGMENT_CLASS}
            onClick={() => setFavoritesOnly(false)}
          >
            전체 모델{" "}
            <span className="font-normal text-grey-600 tabular-nums">
              {choices.length}
            </span>
          </button>
          <button
            type="button"
            aria-label="즐겨찾기 목록"
            aria-pressed={favoritesOnly}
            className={SEGMENT_CLASS}
            onClick={() => setFavoritesOnly(true)}
          >
            즐겨찾기
            {favorites.kind === "ready" && (
              <span className="font-normal text-grey-600 tabular-nums">
                {" "}
                {new Set(favorites.keys).size}
              </span>
            )}
          </button>
        </fieldset>
        <SearchField
          label="모델 검색어"
          placeholder="모델명·제작사·Provider 검색"
          value={query}
          onSearch={setQuery}
        />
        {imagesAttached && (
          <button
            type="button"
            aria-pressed={imagesOnly}
            onClick={() => setImagesOnly(!imagesOnly)}
            className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-label font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              imagesOnly
                ? "border-brand bg-blue-50 text-blue-600"
                : "border-grey-200 bg-white text-grey-700 hover:bg-grey-50"
            }`}
          >
            <span aria-hidden="true">{imagesOnly ? "✓" : "+"}</span>
            이미지 지원만
            <span className="font-normal text-grey-600">
              이미지를 첨부했어요
            </span>
          </button>
        )}
      </div>
      <div
        role="status"
        className="my-4 flex flex-wrap items-center gap-2 rounded-control bg-grey-50 p-3"
      >
        <p className="text-label font-semibold tabular-nums">
          선택 {count} / {MODEL_LIMITS.max}
        </p>
        {pending.length > 0 ? (
          <ul
            aria-label="모달에서 선택한 모델"
            className="flex flex-wrap gap-2"
          >
            {pending.map((key) => {
              const choice = choices.find((item) => item.key === key);
              const label = choice
                ? `${choice.name} · ${choice.provider}`
                : "목록에 없는 모델";
              return (
                <li key={key}>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="bg-white ring-1 ring-grey-200"
                    aria-label={`${label} 선택 해제`}
                    onClick={() => remove(key)}
                  >
                    <ModelCreatorBadge creator={choice?.creator} />
                    {label}
                    {(counts[key] ?? 1) > 1 && (
                      <span className="font-normal tabular-nums">
                        ({counts[key]}개 항목)
                      </span>
                    )}
                    <span aria-hidden="true">×</span>
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-caption text-grey-600">
            아래 목록에서 비교할 모델을 골라 주세요.
          </p>
        )}
        <p className="ml-auto text-caption text-grey-600 tabular-nums">
          {remaining > 0
            ? `${remaining}개 더 고를 수 있어요`
            : "더 고를 수 없어요. 바꾸려면 하나를 해제해 주세요"}
        </p>
        {pending.some(
          (key) =>
            !choices.some((choice) => choice.key === key && choice.selectable),
        ) && (
          <p role="alert" className="basis-full text-caption text-red-600">
            고를 수 없는 모델을 해제하고 다시 골라 주세요.
          </p>
        )}
        {Object.values(counts).some((value) => value > 1) && (
          <p className="basis-full text-caption text-grey-600">
            같은 모델의 비교 항목은 함께 선택·해제돼요. 항목 하나만 빼려면 본문
            카드에서 제거해요.
          </p>
        )}
      </div>
      {favoritesOnly && favorites.kind !== "ready" ? (
        <ModelFavoritesNotice favorites={favorites} />
      ) : (
        <>
          <p
            role="status"
            className="mb-2 text-caption text-grey-600 tabular-nums"
          >
            검색 결과 {matches.length}개
          </p>
          {matches.length > 0 ? (
            <ModelCatalogTable
              choices={matches}
              pending={pending}
              unavailable={unavailable}
              favorites={favorites}
              onToggle={toggle}
              counts={counts}
            />
          ) : (
            <div className="py-8 text-center">
              <p className="font-semibold">{empty.title}</p>
              <p className="mt-1 text-body-sm text-grey-600">
                {empty.description}
              </p>
            </div>
          )}
        </>
      )}
      <p className="mt-3 text-caption text-grey-600">
        별은 즐겨찾기예요. 누르는 즉시 저장되고 선택 적용·닫기와 상관없어요.
      </p>
    </Dialog>,
    document.body,
  );
}
