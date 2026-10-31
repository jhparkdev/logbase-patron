import { useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import { SearchField } from "../../../shared/components/ui/SearchField";
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
import { ModelFavoritesNotice } from "./ModelFavoritesNotice";

export function ModelPickerDialog({
  choices,
  selections,
  unavailable,
  favorites = unavailableFavorites,
  onClose,
  onApply,
}: {
  choices: ModelChoice[];
  selections: string[];
  unavailable: boolean;
  favorites?: ModelFavoritesView;
  onClose: () => void;
  onApply: (keys: string[]) => void;
}) {
  const [pending, setPending] = useState(() => selectedModelKeys(selections));
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const matches = searchFavoriteModels(
    choices,
    query,
    favoritesOnly,
    favorites,
  );
  const empty = emptyCatalogMessage(query, favoritesOnly, favorites);
  const canApply = !unavailable && canApplyModels(pending, choices);
  const remove = (key: string) =>
    setPending((keys) => keys.filter((value) => value !== key));
  const toggle = (key: string) =>
    setPending((keys) => {
      if (keys.includes(key)) return keys.filter((value) => value !== key);
      if (
        unavailable ||
        keys.length >= MODEL_LIMITS.max ||
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
      <p className="mb-4 text-body-sm text-grey-600">
        모델을 {MODEL_LIMITS.min}~{MODEL_LIMITS.max}개 선택해 주세요. 같은
        모델도 Provider가 다르면 비교할 수 있어요.
      </p>
      <SearchField
        label="모델 검색어"
        placeholder="모델명 또는 Provider 검색"
        value={query}
        onSearch={setQuery}
      />
      <fieldset aria-label="모델 목록 범위" className="mt-3 flex gap-2">
        <Button
          size="sm"
          variant="secondary"
          aria-label="전체 모델 목록"
          aria-pressed={!favoritesOnly}
          className="aria-pressed:bg-brand-weak aria-pressed:text-blue-600"
          onClick={() => setFavoritesOnly(false)}
        >
          전체 모델
        </Button>
        <Button
          size="sm"
          variant="secondary"
          aria-label="즐겨찾기 목록"
          aria-pressed={favoritesOnly}
          className="aria-pressed:bg-brand-weak aria-pressed:text-blue-600"
          onClick={() => setFavoritesOnly(true)}
        >
          즐겨찾기
          {favorites.kind === "ready" && (
            <span className="tabular-nums">
              {" "}
              {new Set(favorites.keys).size}
            </span>
          )}
        </Button>
      </fieldset>
      <p className="mt-2 text-caption text-grey-600">
        별 버튼으로 즐겨찾기를 관리해요. 즐겨찾기 변경은 선택 적용·닫기와 별도로
        처리돼요.
      </p>
      <div className="my-4 rounded-control bg-grey-50 p-3">
        <p role="status" className="text-label font-semibold tabular-nums">
          선택한 모델 {pending.length}/{MODEL_LIMITS.max}개
        </p>
        {pending.length > 0 ? (
          <ul
            aria-label="모달에서 선택한 모델"
            className="mt-2 flex flex-wrap gap-2"
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
                    aria-label={`${label} 선택 해제`}
                    onClick={() => remove(key)}
                  >
                    {label}
                    <span aria-hidden="true">×</span>
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-1 text-caption text-grey-600">
            아래 목록에서 비교할 모델을 선택해 주세요.
          </p>
        )}
        {pending.some(
          (key) =>
            !choices.some((choice) => choice.key === key && choice.selectable),
        ) && (
          <p role="alert" className="mt-2 text-caption text-red-600">
            선택할 수 없는 모델을 해제하고 다시 선택해 주세요.
          </p>
        )}
        {pending.length >= MODEL_LIMITS.max && (
          <p className="mt-2 text-caption text-grey-600">
            다른 모델을 고르려면 선택한 모델을 먼저 해제해 주세요.
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
    </Dialog>,
    document.body,
  );
}
