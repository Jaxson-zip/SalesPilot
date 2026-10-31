"use client"

import { DatePicker, FormField, SimpleSelect } from "@/components/biz/FormControls"
import { Input } from "@/components/ui/input"
import { hotelSummary, TRANSPORT_MODE_OPTIONS, type TripErrors, type TripValues } from "@/lib/expense-trip"
import { localDate } from "@/lib/format"
import type { ExpenseType } from "@/types/api"

/** 差旅交通：出发地 / 目的地 / 交通方式（都是选填，便于核对行程） */
function TransportFields({ trip, onChange }: { trip: TripValues; onChange: (t: TripValues) => void }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="出发地" htmlFor="exp-from">
          <Input
            id="exp-from"
            value={trip.from_city}
            maxLength={50}
            placeholder="例如：深圳"
            onChange={(e) => onChange({ ...trip, from_city: e.target.value })}
          />
        </FormField>
        <FormField label="目的地" htmlFor="exp-to">
          <Input
            id="exp-to"
            value={trip.to_city}
            maxLength={50}
            placeholder="例如：北京"
            onChange={(e) => onChange({ ...trip, to_city: e.target.value })}
          />
        </FormField>
      </div>
      <FormField label="交通方式" hint="跨城优先高铁二等座；乘飞机请在事由中说明原因">
        <SimpleSelect
          value={trip.transport_mode}
          onChange={(m) => onChange({ ...trip, transport_mode: m })}
          options={TRANSPORT_MODE_OPTIONS}
          placeholder="选择交通方式"
          ariaLabel="交通方式"
        />
      </FormField>
    </>
  )
}

/** 差旅住宿：城市 + 入住 / 离店日期（必填），自动算晚数和每晚金额，标准由后端按城市判断 */
function HotelFields({
  trip,
  amount,
  errors,
  onChange,
}: {
  trip: TripValues
  amount: string
  errors: TripErrors
  onChange: (t: TripValues) => void
}) {
  const summary = hotelSummary(amount, trip)
  return (
    <>
      <FormField label="住宿城市" required error={errors.city} htmlFor="exp-city">
        <Input
          id="exp-city"
          value={trip.city}
          maxLength={50}
          placeholder="例如：北京"
          aria-invalid={Boolean(errors.city) || undefined}
          onChange={(e) => onChange({ ...trip, city: e.target.value })}
        />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="入住日期" required error={errors.check_in}>
          <DatePicker
            value={trip.check_in}
            onChange={(d) => onChange({ ...trip, check_in: d })}
            ariaLabel="入住日期"
            max={localDate()}
          />
        </FormField>
        <FormField label="离店日期" required error={errors.check_out}>
          <DatePicker
            value={trip.check_out}
            onChange={(d) => onChange({ ...trip, check_out: d })}
            ariaLabel="离店日期"
            max={localDate()}
          />
        </FormField>
      </div>
      {summary ? (
        <div aria-live="polite" data-testid="expense-nights" className="text-zinc-600 tabular-nums">
          {summary}
        </div>
      ) : null}
    </>
  )
}

/** 按费用类型显示差旅补充信息；客户招待和其他类型不显示 */
export function TripFields({
  type,
  trip,
  amount,
  errors,
  onChange,
}: {
  type: ExpenseType
  trip: TripValues
  amount: string
  errors: TripErrors
  onChange: (t: TripValues) => void
}) {
  if (type === "transport") return <TransportFields trip={trip} onChange={onChange} />
  if (type === "hotel") return <HotelFields trip={trip} amount={amount} errors={errors} onChange={onChange} />
  return null
}
