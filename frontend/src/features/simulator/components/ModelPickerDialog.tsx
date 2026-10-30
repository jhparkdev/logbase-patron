import { useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import { SearchField } from "../../../shared/components/ui/SearchField";
import { MODEL_LIMITS } from "../lib/limits";
import {
  canApplyModels,
  searchModels,
  selectedModelKeys,
} from "../lib/model-selection";
import type { ModelChoice } from "../lib/presentation";

export function ModelPickerDialog({
  choices,
  selections,
  unavailable,
  onClose,
  onApply,
}: {
  choices: ModelChoice[];
  selections: string[];
  unavailable: boolean;
  onClose: () => void;
  onApply: (keys: string[]) => void;
}) {
  const [pending, setPending] = useState(() => selectedModelKeys(selections));
  const [query, setQuery] = useState("");
  const matches = searchModels(choices, query);
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
      <p role="status" className="mb-2 text-caption text-grey-600 tabular-nums">
        검색 결과 {matches.length}개
      </p>
      {matches.length > 0 ? (
        <div className="max-h-64 overflow-y-auto rounded-control border border-grey-200">
          <table className="w-full text-left text-body-sm">
            <caption className="sr-only">비교할 모델 카탈로그</caption>
            <thead className="sticky top-0 bg-grey-50 text-label text-grey-600">
              <tr>
                <th scope="col" className="p-3">
                  선택
                </th>
                <th scope="col" className="p-3">
                  모델
                </th>
                <th scope="col" className="p-3">
                  Provider
                </th>
                <th scope="col" className="p-3">
                  입력 지원
                </th>
              </tr>
            </thead>
            <tbody>
              {matches.map((choice) => {
                const checked = pending.includes(choice.key);
                return (
                  <tr
                    key={choice.key}
                    className="border-t border-grey-100 hover:bg-grey-50"
                  >
                    <td className="p-3">
                      <input
                        type="checkbox"
                        aria-label={`${choice.name} · ${choice.provider}`}
                        checked={checked}
                        disabled={
                          unavailable ||
                          (!checked &&
                            (!choice.selectable ||
                              pending.length >= MODEL_LIMITS.max))
                        }
                        onChange={() => toggle(choice.key)}
                        className="size-4 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                      />
                    </td>
                    <th scope="row" className="p-3 font-semibold">
                      {choice.name}
                      {!choice.selectable && (
                        <p className="mt-1 text-caption font-normal text-grey-600">
                          {choice.unavailableReason ?? "선택 불가"}
                        </p>
                      )}
                    </th>
                    <td className="p-3 text-grey-700">{choice.provider}</td>
                    <td className="p-3 text-grey-600">
                      {choice.supportsImages ? "텍스트·이미지" : "텍스트"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="py-8 text-center">
          <p className="font-semibold">
            {query ? "검색 결과가 없어요" : "선택할 수 있는 모델이 없어요"}
          </p>
          <p className="mt-1 text-body-sm text-grey-600">
            {query
              ? "다른 모델명이나 Provider로 검색해 주세요."
              : "AI 모델 관리에서 모델 목록을 확인해 주세요."}
          </p>
        </div>
      )}
    </Dialog>,
    document.body,
  );
}
