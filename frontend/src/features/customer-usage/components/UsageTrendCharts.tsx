import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCount, formatUsd } from "../../../shared/lib/format";
import { type TrendPointView, unreflectedText } from "../lib/view";

const SYNC_ID = "customer-usage-trend";
const TASK_CHART_HEIGHT = 150;
const COST_CHART_HEIGHT = 190;
const Y_AXIS_WIDTH = 44;
const TASK_COLOR = "var(--color-blue-500)";
const CONFIRMED_COLOR = "var(--color-blue-700)";
const ESTIMATED_COLOR = "var(--color-blue-300)";
const GRID_COLOR = "var(--color-grey-100)";
const AXIS_TICK = { fontSize: 12, fill: "var(--color-grey-600)" };

/** 날짜를 맞춘 그래프 두 개. 같은 값을 표로도 두므로 화면 낭독기에는 숨긴다. */
export function UsageTrendCharts({ points }: { points: TrendPointView[] }) {
  return (
    <>
      <figure aria-hidden="true">
        <figcaption className="mb-2 text-label font-medium text-grey-700">
          작업 건수 <span className="font-normal text-grey-600">(건)</span>
        </figcaption>
        <ResponsiveContainer width="100%" height={TASK_CHART_HEIGHT}>
          <BarChart data={points} syncId={SYNC_ID}>
            <CartesianGrid vertical={false} stroke={GRID_COLOR} />
            <XAxis dataKey="day" hide />
            <YAxis
              width={Y_AXIS_WIDTH}
              allowDecimals={false}
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: GRID_COLOR }} content={<TaskTooltip />} />
            <Bar
              dataKey="tasks"
              fill={TASK_COLOR}
              radius={[2, 2, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </figure>
      <figure aria-hidden="true">
        <figcaption className="mb-2 text-label font-medium text-grey-700">
          API 비용 <span className="font-normal text-grey-600">(USD)</span>
        </figcaption>
        <ResponsiveContainer width="100%" height={COST_CHART_HEIGHT}>
          <BarChart data={points} syncId={SYNC_ID}>
            <CartesianGrid vertical={false} stroke={GRID_COLOR} />
            <XAxis
              dataKey="day"
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              width={Y_AXIS_WIDTH}
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip cursor={{ fill: GRID_COLOR }} content={<CostTooltip />} />
            <Legend
              align="left"
              verticalAlign="top"
              iconType="square"
              iconSize={10}
              itemSorter="dataKey"
              wrapperStyle={{ fontSize: 12, paddingBottom: 8 }}
            />
            <Bar
              name="확정"
              dataKey="confirmed"
              stackId="cost"
              fill={CONFIRMED_COLOR}
              isAnimationActive={false}
            />
            <Bar
              name="추정"
              dataKey="estimated"
              stackId="cost"
              fill={ESTIMATED_COLOR}
              isAnimationActive={false}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </figure>
    </>
  );
}

type TrendTooltipProps = {
  active?: boolean;
  payload?: readonly { payload?: TrendPointView }[];
};

function TooltipBox({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg bg-grey-800 px-3 py-2 text-caption text-white tabular-nums">
      {children}
    </div>
  );
}

function TaskTooltip({ active, payload }: TrendTooltipProps) {
  const point = payload?.[0]?.payload;
  if (!active || point === undefined) {
    return null;
  }
  return (
    <TooltipBox>
      <p className="font-bold">{point.date}</p>
      <p>작업 {formatCount(point.tasks)}건</p>
    </TooltipBox>
  );
}

function CostTooltip({ active, payload }: TrendTooltipProps) {
  const point = payload?.[0]?.payload;
  if (!active || point === undefined) {
    return null;
  }
  const unreflected = unreflectedText(point.unknownCount);
  return (
    <TooltipBox>
      <p className="font-bold">{point.date}</p>
      <p>확정 {formatUsd(point.confirmedText, "summary")}</p>
      <p>추정 ≈ {formatUsd(point.estimatedText, "summary")}</p>
      {unreflected && <p className="text-yellow-200">{unreflected}</p>}
    </TooltipBox>
  );
}
