import type { components } from "./api.generated";
export type CaseRecord = Omit<
  components["schemas"]["CaseView"],
  "details" | "checks"
> & {
  details: Record<string, unknown>;
  checks: { label: string; passed: boolean }[];
};
export type Product = {
  id: string;
  name: string;
  description: string;
  category: string;
  price_paise: number;
  stock: number;
  reserved_stock: number;
  available_stock: number;
  options: Record<string, unknown>;
};
export type Order = {
  id: string;
  customer_name: string;
  product_name: string;
  customer_id: string;
  product_id: string;
  status: string;
  delivery_status: string;
  total_paise: number;
  paid_paise: number;
  refunded_paise: number;
  customizations: Record<string, unknown>[];
};
export type Message = {
  id: string;
  role: string;
  body: string;
  status: string;
  created_at: string;
  case_ids: string[];
  provider_id: string | null;
};
export type Conversation = {
  id: string;
  customer_name: string;
  customer_id: string;
  order_id: string | null;
  handoff: boolean;
  channel: string;
  messages: Message[];
};
export type Rules = {
  return_window_days: number;
  auto_refund_limit_paise: number;
  pickup: string;
  engraving_requires_approval: boolean;
  cancellation_before_shipping: boolean;
  warranty_days: number;
  delivery_fee_paise: number;
  tax_basis_points: number;
  return_permission: string;
  refund_permission: string;
  redelivery_permission: string;
  customization_permission: string;
  return_reasons: string[];
  require_return_inspection: boolean;
  require_photo: boolean;
  engraving_paise: number;
  gift_wrap_paise: number;
  preparation_days: number;
  proposal_hours: number;
};
export type Recommendation = {
  text: string;
  tradeoff: string;
  case_ids: string[];
  count: number;
  recurring: boolean;
};
export type Workspace = {
  merchant: {
    id: string;
    name: string;
    settings: { location?: string; support_email?: string };
  };
  customers: { id: string; name: string; phone: string }[];
  products: Product[];
  orders: Order[];
  conversations: Conversation[];
  cases: CaseRecord[];
  policies: {
    id: string;
    version: number;
    rules: Rules;
    published: boolean;
    created_at: string;
  }[];
  slots: {
    id: string;
    label: string;
    location: string;
    capacity: number;
    reserved: number;
    starts_at: string;
    ends_at: string;
  }[];
  reservations: {
    id: string;
    case_id: string;
    order_id: string;
    slot_id: string;
    status: string;
    attempts: number;
  }[];
  reviews: {
    id: string;
    case_id: string;
    product_id: string;
    author: string;
    rating: number;
    body: string;
    topic: string;
    source: string;
  }[];
  evidence: {
    id: string;
    case_id: string | null;
    conversation_id: string;
    filename: string;
    assessment: string;
    created_at: string;
    verified: boolean;
  }[];
  audit_logs: {
    id: string;
    actor: string;
    action: string;
    entity_id: string;
    detail: Record<string, unknown>;
    created_at: string;
  }[];
  refunds: {
    id: string;
    case_id: string;
    order_id: string;
    amount_paise: number;
    status: string;
    provider: string;
  }[];
  returns: {
    id: string;
    case_id: string;
    order_id: string;
    status: string;
    reason: string;
    restocked: boolean;
  }[];
  operations: {
    id: string;
    case_id: string;
    kind: string;
    status: string;
    provider: string;
    detail: Record<string, unknown>;
  }[];
  metrics: {
    total: number;
    resolved: number;
    ongoing: number;
    flagged: number;
    resolution_rate: number | null;
    ai_share: number | null;
    median_resolution_hours: number | null;
    rating: number | null;
    review_count: number;
  };
  insights: {
    topic: string;
    title: string;
    count: number;
    description: string;
    case_ids: string[];
    recurring: boolean;
  }[];
  reports: {
    id: string;
    date_from: string;
    date_to: string;
    generated_at: string;
    mode: string;
    body: { summary: string; recommendations: Recommendation[] };
  }[];
  date_range: { from: string; to: string; timezone: string; basis: string };
  mode: {
    demo: boolean;
    ai: string;
    whatsapp: boolean;
    storage: string;
    service_status: string;
    worker_alive: boolean;
    failed_jobs: number;
  };
};
export type Mutate = (
  path: string,
  body?: unknown,
  method?: string,
) => Promise<void>;
export type ScreenProps = {
  data: Workspace;
  onCase: (id: string) => void;
  search?: string;
};
