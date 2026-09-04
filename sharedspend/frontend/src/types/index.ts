// ─── Enums ────────────────────────────────────────────────────────────────────
export type TransactionType = 'SHARED' | 'PERSONAL'
export type MemberRole = 'OWNER' | 'MEMBER'

// ─── Auth ─────────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  display_name?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RefreshRequest {
  refresh_token: string
}

// ─── User ─────────────────────────────────────────────────────────────────────
export interface UserOut {
  id: string
  username: string
  email: string
  display_name: string
  is_active: boolean
  created_at: string
}

export interface UserUpdate {
  display_name?: string
  email?: string
}

export interface PasswordChange {
  old_password: string   // backend field name
  new_password: string
}

// ─── Group ────────────────────────────────────────────────────────────────────
export interface GroupCreate {
  name: string
  description?: string
  currency?: string
}

export interface GroupUpdate {
  name?: string
  description?: string
}

export interface GroupOut {
  id: string
  name: string
  description: string | null
  currency: string
  owner_id: string
  created_at: string
}

/** Backend MemberOut — includes display_name and username for UI display */
export interface GroupMemberOut {
  id: string
  group_id: string
  user_id: string
  display_name: string | null
  username: string | null
  role: MemberRole
  joined_at: string
}

export interface GroupDetailOut extends GroupOut {
  members: GroupMemberOut[]
}

export interface InviteMember {
  username: string
}

// ─── Budget ───────────────────────────────────────────────────────────────────
export interface BudgetPeriodCreate {
  year: number
  month: number
  amount: number
}

export interface BudgetPeriodOut {
  id: string
  group_id: string
  year: number
  month: number
  amount: number
  created_at: string
}

// ─── Category ─────────────────────────────────────────────────────────────────
export interface CategoryCreate {
  name: string
  icon?: string
  keyword_hints?: string[]
}

export interface CategoryUpdate {
  name?: string
  icon?: string
  keyword_hints?: string[]
}

export interface CategoryOut {
  id: string
  name: string
  icon: string | null
  is_global: boolean
  group_id: string | null
  keyword_hints: string[] | null
  created_at: string
}

export interface CategoryDeleteRequest {
  reassign_to_category_id?: string | null
}

// ─── Categorizer ──────────────────────────────────────────────────────────────
export interface CategorizeRequest {
  description: string
}

export interface CategorizeResponse {
  category_id: string | null
  category_name: string | null
  confidence: string   // "rule_match" | "no_match"
}

// ─── Transaction ──────────────────────────────────────────────────────────────
export interface TransactionCreate {
  description: string
  amount: number
  date: string // YYYY-MM-DD
  type: TransactionType
  category_id?: string | null
  group_id?: string | null
  payer_id?: string | null
  notes?: string | null
  add_to_settlement?: boolean
}

export interface TransactionUpdate {
  description?: string
  amount?: number
  date?: string
  type?: TransactionType
  category_id?: string | null
  group_id?: string | null
  payer_id?: string | null
  notes?: string | null
  add_to_settlement?: boolean
}

/** Matches backend TransactionOut exactly */
export interface TransactionOut {
  id: string
  description: string
  amount: number
  date: string
  type: TransactionType
  category_id: string | null
  group_id: string | null
  payer_id: string | null
  recorded_by_id: string
  suggested_category_id: string | null
  notes: string | null
  add_to_settlement: boolean
  is_deleted: boolean
  created_at: string
  updated_at: string
}

/** Frontend-normalized paginated response (constructed in api/transactions.ts) */
export interface TransactionListResponse {
  items: TransactionOut[]
  total: number
  page: number
  page_size: number
}

// ─── Transaction filters ───────────────────────────────────────────────────────
export interface TransactionFilters {
  group_id?: string
  type?: TransactionType
  category_id?: string
  date_from?: string
  date_to?: string
  year?: number
  month?: number
  week?: number
  page?: number
  page_size?: number
  search?: string
}

// ─── Analytics ────────────────────────────────────────────────────────────────
export interface AnalyticsFilters {
  group_id: string
  year?: number
  month?: number
  week?: number
  date_from?: string
  date_to?: string
}

export interface MemberPersonal {
  user_id: string
  display_name: string | null
  personal_spent: number
}

export interface MemberPaid {
  user_id: string
  display_name: string | null
  paid: number
}

/** Matches backend SummaryOut */
export interface BudgetSummary {
  budget: number | null
  shared_spent: number
  remaining: number | null
  utilization_pct: number | null
  personal_by_member: MemberPersonal[]
  paid_by_member: MemberPaid[]
}

/** Matches backend CategorySpend */
export interface CategorySpend {
  category_id: string | null
  category_name: string | null
  amount: number
  count: number
}

/** Daily spend — matches backend DailySpend */
export interface DailySpend {
  date: string
  shared: number
  personal: number
}

/** Weekly spend — matches backend WeeklySpend */
export interface WeeklySpend {
  year: number
  week: number
  shared: number
  personal: number
}

/** Monthly spend — matches backend MonthlySpend */
export interface MonthlySpend {
  year: number
  month: number
  shared: number
  personal: number
}

/** Yearly spend — matches backend YearlySpend */
export interface YearlySpend {
  year: number
  shared: number
  personal: number
}

/** Matches backend MemberContribution */
export interface MemberContribution {
  user_id: string
  display_name: string | null
  paid: number
  personal_spent: number
}

export interface HighestItem {
  name: string | null
  amount: number
  date: string | null
}

/** Matches backend InsightsOut */
export interface InsightsOut {
  highest_category: HighestItem | null
  highest_day: HighestItem | null
  largest_transactions: TransactionOut[]
  trend: string | null
}

/** Matches backend ForecastOut */
export interface ForecastOut {
  projected_spend: number | null
  budget: number | null
  on_track: boolean | null
  days_elapsed: number
  days_in_month: number
}

// ─── Settlement ───────────────────────────────────────────────────────────────
export type SettlementStatus = 'PENDING' | 'SETTLED'

/** Calculated transfer (not persisted) returned by /settlements/groups/{id}/calculate */
export interface SettlementTransfer {
  from_user_id: string
  to_user_id: string
  amount: number
}

/** Persisted settlement record from the backend */
export interface SettlementRecordOut {
  id: string
  group_id: string
  from_user_id: string
  to_user_id: string
  amount: number
  status: SettlementStatus
  settled_at: string | null
  created_at: string
}
