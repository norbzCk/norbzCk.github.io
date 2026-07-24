# System Architecture Review

## Current Product Intent

This system is evolving from a sales dashboard into a multi-role commerce and fulfillment platform with these actors:

- Customer: browse products, place orders, pay, track delivery, raise disputes
- Business/Seller: manage inventory, accept and fulfill orders, assign logistics, communicate with customers
- Logistics: receive assignments, update delivery status, share location, complete proof of delivery
- Super admin: monitor marketplace activity, verification, and operational health

That is the right direction for a large marketplace-style system.

## What Already Exists

The current codebase already has strong building blocks:

- Role-based accounts for customer, seller, logistics, and super admin
- Order lifecycle states and seller operations
- Payment records and payment-gated fulfillment
- Delivery assignment and live tracking fields
- Notification feeds
- A real-time delivery WebSocket for chat and tracking
- Seller, logistics, and customer-facing pages

This means the product intent is clear and the platform has a usable foundation.

## Implementation status

The repository already contains many of the recommended domain and runtime pieces:

- A normalized order domain with `orders`, `order_items`, `order_status_history`, `inventory_reservations`, `payment_attempts`, `payment_transactions`, `shipment_events`, and `audit_logs`.
- Legacy `Sale` records remain for compatibility, but new orders and order items are created and linked during checkout.
- Order creation uses row-level stock locking via `SELECT ... FOR UPDATE` and supports `Idempotency-Key` reuse.
- Persistent chat threads are stored in `conversation_threads`, `conversation_messages`, and `message_receipts`.
- Live delivery websocket traffic includes chat, typing, location updates, and receipt/read state handling.
- Delivery failure is tracked explicitly as `Delivery Failed` and written into order status history.

## Key Gaps Blocking a Large-Scale Production System

### 1. Order processing has stronger concurrency controls, but full checkout scale remains incomplete

The current code now protects stock updates with row-level locking during checkout and supports idempotent order creation using `Idempotency-Key`. That improves safety for single-product checkout paths.

Remaining risk:

- multi-item cart atomicity is not fully implemented yet
- payment callback idempotency and async retry handling are still sparse
- full database transaction boundary hardening across order + delivery + payment is not complete

Relevant code:

- `backend/app/sales.py`
- `backend/app/payments.py`
- `backend/app/business.py`

### 2. The order model is now normalized, but the checkout surface still retains a legacy `Sale` facade

The backend has been refactored with separate `orders`, `order_items`, `order_status_history`, `inventory_reservations`, `payment_attempts`, `payment_transactions`, and other operational tables.

Current limitation:

- customer checkout still only supports a single item per order
- `Sale` remains active as a compatibility record, so the transition is not yet fully completed

### 3. Chat exists and is now persisted, but UX-level threading may still need polish

The delivery websocket now provides a real persistent conversation thread backed by database tables:

- chat messages persist in `conversation_messages`
- typing indicators are handled and broadcast by the backend websocket
- receipt/read events are recorded in `message_receipts`
- order threads are created and maintained via `ensure_order_thread`
- delivery location updates are broadcast alongside chat traffic

Remaining improvement:

- the frontend experience should be verified to ensure shared thread inbox semantics across customer, seller, logistics, and support

#No results for the active editor
## 4. Delivery failure state is now handled explicitly

The current code treats `Delivery Failed` as a valid status in normalization and writes it into status history during logistics failure events.

Remaining work:

- ensure all UI views and reports display `Delivery Failed` consistently instead of collapsing it into completed or cancelled states

### 5. Production operations are still in startup-mode

The backend is still doing schema patching at startup and the app stores uploads on the local service filesystem. For a serious production system, those are operational risks:

- deployment-time schema drift
- hard-to-track environment differences
- fragile recoverability
- non-durable uploaded files across redeploys

## Target Business Flow

### Customer order flow

1. Customer adds one or more items to cart (current checkout implementation supports a single item per order)
2. Checkout creates an `Order`
3. System creates one or more `OrderItem` records
4. Inventory is reserved atomically
5. Payment intent is created
6. Seller receives order task
7. Seller accepts or rejects
8. If accepted, fulfillment moves to packaging
9. Delivery request is created
10. Logistics is assigned automatically or manually
11. Customer, seller, and logistics can communicate inside the order thread
12. Delivery status and proof are captured
13. Order is completed, rated, and audited

### Seller operational flow

1. Seller sees a queue of new paid orders
2. Seller processes multiple orders in parallel
3. Orders are prioritized by SLA, payment status, delivery promise, and stock readiness
4. Seller can reassign logistics, update delivery instructions, and chat within the order thread
5. Exceptions are escalated into dispute or support workflows

### Logistics operational flow

1. Logistics receives a dispatch task
2. Accepts assignment
3. Pickup confirmed
4. Live location and milestone updates are published
5. Delivery proof is captured
6. COD collection is recorded where relevant
7. Failed deliveries enter exception workflow with reason and reattempt policy

## Recommended Core Architecture

### Domain model

Add these core entities:

- `orders`
- `order_items`
- `shipments`
- `shipment_events`
- `order_status_history`
- `conversation_threads`
- `conversation_participants`
- `conversation_messages`
- `message_receipts`
- `inventory_reservations`
- `payment_attempts`
- `audit_logs`

### Service boundaries

Keep a modular monolith first, with clean internal boundaries:

- Identity and access
- Catalog and inventory
- Checkout and orders
- Payments
- Fulfillment and logistics
- Messaging and notifications
- Disputes and support
- Analytics and marketplace intelligence

That is the best next step before moving to microservices. The current system is not ready to benefit from a distributed architecture yet.

### Event-driven workflow

Introduce internal domain events for operational decoupling:

- `order.created`
- `payment.completed`
- `order.accepted`
- `order.packed`
- `shipment.assigned`
- `shipment.picked_up`
- `shipment.failed`
- `shipment.delivered`
- `message.sent`
- `dispute.opened`

These events should drive notifications, analytics updates, SLA tracking, and live UI refresh.

## Non-Functional Requirements for an A-Grade System

### Scalability

- atomic stock reservation with row locking
- idempotent checkout and payment callbacks
- queue-backed async jobs for notifications, analytics refresh, and dispatch
- pagination on all operational lists
- websocket connection management with persistent message storage

### Reliability

- Alembic-only schema evolution
- retry-safe payment and notification flows
- dead-letter strategy for failed async jobs
- durable object storage for uploads
- health checks for app, database, queue, and websocket broker

### Performance

- indexes on `order_id`, `seller_id`, `buyer_id`, `status`, `created_at`
- precomputed operational dashboards where needed
- N+1 query review on order aggregation endpoints
- caching for catalog and marketplace overview reads

### Security

- stronger production secret management
- token rotation / revocation strategy
- role-based authorization at every order/thread action
- audit logs for sensitive actions
- rate limiting on auth, checkout, chat, and tracking endpoints

### Observability

- structured logs with correlation IDs
- metrics for order throughput, payment success, assignment latency, chat delivery, delivery SLA
- traceable event history per order
- alerting for failed payments, dispatch backlog, websocket failure rate, and stock anomalies

### Usability

- shared thread per order for customer, seller, logistics, and support
- delivery ETA and exception visibility
- clear seller work queues: new, paid, packing, awaiting dispatch, in transit, failed, completed
- customer self-service: cancel, track, chat, dispute, rate

## Highest-Priority Implementation Steps

### Phase 1: Data correctness

- Split `Sale` into `Order` + `OrderItem`
- Add foreign keys and indexes
- Add `order_status_history`
- Make order creation transactional and concurrency-safe
- Make delivery assignment transactional and concurrency-safe

### Phase 2: Communication and operations

- Add persistent chat tables
- Save every message and delivery event
- Support typing, delivery receipts, and read receipts end to end
- Expose chat to customer, seller, logistics, and support from the same thread
- Replace the seller communication placeholder feed with real conversation threads

### Phase 3: Fulfillment scale

- Add dispatch queue and assignment rules
- Add inventory reservation and release logic
- Add shipment retries / reattempt workflow
- Add SLA-based prioritization and exception handling

### Phase 4: Production hardening

- move schema changes to Alembic migrations only
- move uploads to object storage
- add background worker / queue
- add structured logging, metrics, and alerts
- add automated integration tests for multi-user concurrency paths

## Final Assessment

The current system already matches the intended business direction at a feature-foundation level, and several previously identified gaps are now implemented in the backend.

The most important remaining work is:

- completing multi-item cart and split-order checkout support
- moving schema management to Alembic-only migrations and removing runtime schema patching
- replacing local filesystem uploads with durable object storage
- adding async queue/backlog handling, metrics, and production observability
- validating the full shared order thread UX across customer, seller, logistics, and support

The current backend does now include:

- transactional stock locking and order idempotency for single-item checkout
- a normalized order domain with persistence tables for orders, items, status history, reservations, payments, and shipment events
- persistent websocket chat with typing and read/delivery receipts
- explicit `Delivery Failed` handling and status history logging

- operational resilience and observability

Once those are implemented, this can become a strong marketplace operations system that supports many simultaneous customers, keeps sellers and logistics coordinated, and gives customers a smoother, more trustworthy experience.
