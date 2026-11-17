import type { components } from "./schema";

type S = components["schemas"];

export type Ticket = S["TicketRead"];
export type TicketEvent = S["TicketEventRead"];
export type TicketPhoto = S["TicketPhotoRead"];
export type TicketStatus = S["TicketStatus"];
export type TicketPriority = S["TicketPriority"];
export type TicketCreate = S["TicketCreate"];
export type TicketLocation = S["TicketLocation"];
export type PhotoKind = S["PhotoKind"];
export type Role = S["Role"];
export type User = S["UserRead"];
export type UserCreate = S["UserCreate"];
export type UserUpdate = S["UserUpdate"];
export type Site = S["SiteRead"];
export type SiteCreate = S["SiteCreate"];
export type Provider = S["ProviderRead"];
export type ProviderCreate = S["ProviderCreate"];
export type SiteStats = S["SiteStats"];
export type Dashboard = S["DashboardReport"];
export type TokenPair = S["TokenPair"];
