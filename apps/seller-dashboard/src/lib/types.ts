export type Product = {
  id: string;
  name: string;
  description: string;
  category: string;
  price_paise: number;
  stock: number;
  options: Record<string, unknown>;
};
export type Order = {
  id: string;
  customer_name: string;
  product_name: string;
  product_id: string;
  status: string;
  delivery_status: string;
  total_paise: number;
  paid_paise: number;
  refunded_paise: number;
  customizations: Record<string, unknown>[];
};
import type { components } from "./api.generated";
export type CaseRecord = components["schemas"]["CaseView"];
export type Message = {
  id: string;
  role: string;
  body: string;
  status: string;
  created_at: string;
};
export type Conversation = {
  id: string;
  customer_name: string;
  order_id: string;
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
};
export type Workspace = {
  merchant: {
    id: string;
    name: string;
    settings: {
      location?: string;
      support_email?: string;
      insight_report?: {
        summary: string;
        recommendations: string[];
        generated_at: string;
        mode: string;
      };
    };
  };
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
  }[];
  reservations: {
    id: string;
    order_id: string;
    slot_id: string;
    status: string;
    attempts: number;
  }[];
  reviews: {
    id: string;
    product_id: string;
    author: string;
    rating: number;
    body: string;
    topic: string;
    source: string;
  }[];
  evidence: {
    id: string;
    conversation_id: string;
    filename: string;
    assessment: string;
    created_at: string;
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
    order_id: string;
    amount_paise: number;
    status: string;
    provider: string;
  }[];
  metrics: {
    orders: number;
    pending: number;
    completed: number;
    open: number;
    rating: number;
    paid_paise: number;
  };
  insights: { title: string; count: number; description: string }[];
  mode: { demo: boolean; ai: string; whatsapp: boolean; storage: string };
};
export type Mutate = (
  path: string,
  body: unknown,
  method?: string,
) => Promise<void>;
