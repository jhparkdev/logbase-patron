import { Button } from "../../../shared/components/ui/Button";
import { Notice } from "../../../shared/components/ui/Notice";
import { useNewModelNotice } from "../hooks/useNewModelNotice";

type NewModelNoticeProps = {
  /** 신규 모델 등록 패널을 여는 동작 */
  onRegister: () => void;
};

/** 최근 OpenRouter에 올라온 미등록 모델을 알리는 띠. 알릴 것이 없으면 그리지 않음 */
export function NewModelNotice({ onRegister }: NewModelNoticeProps) {
  const notice = useNewModelNotice();
  if (!notice) return null;
  return (
    <Notice
      title={notice.title}
      description={notice.description}
      action={
        <Button variant="secondary" size="sm" onClick={onRegister}>
          등록하러 가기
        </Button>
      }
    />
  );
}
