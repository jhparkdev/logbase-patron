import { Result } from "../../../shared/components/ui/Result";

/** 조회 조건에 맞는 API 사용 내역이 없을 때. 비용 추이와 상세 이력이 함께 쓴다. */
export function NoUsageResult() {
  return (
    <Result
      title="이 조건에는 API 사용 내역이 없어요"
      description="기간을 넓히거나 프로젝트·모델 조건을 바꿔 보세요."
    />
  );
}
