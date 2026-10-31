import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { SubscriptionForm } from "./SubscriptionForm";

type SubscriptionPanelProps = {
  /** 적용 월의 처음 값 "YYYY-MM" */
  month: string;
  onClose: () => void;
};

/** 구독료 등록 패널. 등록은 구독료 API가 생기면 연결한다. */
export function SubscriptionPanel({ month, onClose }: SubscriptionPanelProps) {
  return (
    <SidePanel title="구독료 등록" onClose={onClose}>
      <SubscriptionForm defaultMonth={month} onClose={onClose} />
    </SidePanel>
  );
}
