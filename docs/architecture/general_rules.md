# Quick Reference

A scannable reference for daily use. For full explanations, see architecture_design_foundation.md.

---
## The Dependency Rule

> Source code dependencies must point inward — toward the domain. The domain never depends on infrastructure.

This is the single structural rule that underpins everything else.

---
## Layers

| Layer                 | Responsibility                                | Depends On          | Example Contents                                                                                  |
|-----------------------|-----------------------------------------------|---------------------|---------------------------------------------------------------------------------------------------|
| **Presentation / UI** | User interaction, input/output formatting     | Application         | HTTP controllers, CLI handlers, view templates, API endpoint definitions                          |
| **Application**       | Use case orchestration, workflow coordination | Domain              | Application services, use case interactors, command/query handlers                                |
| **Domain**            | Business rules, domain model                  | Nothing             | Entities, value objects, domain services, domain events, repository interfaces, specifications    |
| **Infrastructure**    | Technical capabilities, external integrations | Domain, Application | Repository implementations, ORM configuration, API clients, message queue adapters, email senders |

---
## Building Blocks

### Entities

- Have a **persistent identity** that remains stable across state changes.
- Equality is based on identity, not attributes.
- Have lifecycle (created → modified → archived/deleted).
- *Example:* `Customer(id="C-1234")` — still the same customer even after a name or address change.

### Value Objects

- Defined entirely by their **attributes**. No identity.
- **Immutable.** Need different values? Create a new instance.
- Equality is based on all attribute values.
- Good location for self-contained computations.
- *Example:* `Money(amount=100, currency="USD")` — two instances with the same values are interchangeable.

### Aggregates

- A cluster of entities and value objects treated as a **single unit** for data changes.
- One entity is the **aggregate root** — the only entry point for external access.
- The root enforces all invariants for the aggregate.
- External objects reference only the root.
- Keep aggregates **small**. The boundary = the smallest group that must be immediately consistent.
- Deleting the root deletes everything inside.

### Domain Services

- **Stateless** operations that represent domain concepts.
- Used when an operation spans multiple entities/value objects and doesn't naturally belong to any one of them.
- Part of the domain layer (distinct from application services and infrastructure services).
- *Example:* `TransferFunds(from_account, to_account, amount)`.

### Repositories

- Provide the illusion of an **in-memory collection** of aggregate roots.
- **Interface** defined in the domain layer. **Implementation** in the infrastructure layer.
- Operate on aggregate roots, not arbitrary internal objects.
- This is the primary mechanism for applying the Dependency Rule to persistence.

### Factories

- Encapsulate **complex creation logic** for entities and aggregates.
- Ensure objects are created in a valid state with all invariants satisfied.
- Use when construction involves multiple steps, identity generation, or conditional assembly.
- Use a plain constructor when creation is simple.

### Modules

- Organizational grouping of related domain concepts.
- High cohesion within, low coupling between.
- Names should be part of the ubiquitous language.

---
## Strategic Design

### Bounded Context

- An explicit boundary within which a model is internally consistent and the ubiquitous language applies.
- The same term can mean different things in different bounded contexts.
- Not a module — a bounded context *contains* modules.

### Context Map

- A document (diagram or written) showing all bounded contexts and their relationships.
- Answers: who depends on whom? Where does translation happen?

### Integration Patterns

| Pattern                  | When to Use                                         | Key Characteristic                                             |
|--------------------------|-----------------------------------------------------|----------------------------------------------------------------|
| **Shared Kernel**        | Two teams need to share a small model subset        | Requires coordination on changes; high coupling                |
| **Customer-Supplier**    | One context depends on another; teams can cooperate | Upstream plans with downstream needs in mind                   |
| **Conformist**           | Upstream team won't or can't accommodate downstream | Downstream adopts upstream's model as-is                       |
| **Anticorruption Layer** | Integrating with a legacy or external system        | Translation layer prevents external model from infecting yours |
| **Separate Ways**        | No meaningful integration needed                    | Contexts evolve independently; hard to reconnect later         |
| **Open Host Service**    | Many contexts need to integrate with yours          | Stable, shared protocol; avoids one-off translators            |

---
## Key Refactoring Concepts

### Making Implicit Concepts Explicit

| Signal                                                   | What to Do                                                  |
|----------------------------------------------------------|-------------------------------------------------------------|
| The team discusses a concept that doesn't appear in code | Introduce a class or object for it                          |
| A section of code is convoluted for no obvious reason    | Look for a missing concept whose absence forces workarounds |
| Domain experts contradict each other                     | Dig in — the resolution often reveals a hidden concept      |
### Three Patterns for Explicitness

- **Constraint** — Extract invariant logic into a named method or object. `is_space_available()` instead of inline `size + 1 <= capacity`.
- **Process** — Model multistep domain workflows as explicit domain services. Use Strategy pattern for alternative execution paths.
- **Specification** — Extract complex validation/selection rules into composable specification objects.

---
## Domain Events

- Represent something that **happened** in the domain.
- Immutable, named in past tense (`OrderPlaced`, `PaymentReceived`).
- Part of the domain model (not infrastructure events).
- Useful for decoupling aggregates and for distributed systems.

---
## Distillation

- **Core Domain** — The part of the model that is most central to the business's value. Assign your best developers here.
- **Generic Subdomain** — Necessary but not unique (auth, routing, currency). Can be off-the-shelf, outsourced, or kept simple.

---
## Common Pitfalls

| Pitfall                  | What It Looks Like                                                        | Remedy                                                                                        |
|--------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| **Anemic Domain Model**  | Entities are pure data holders; all logic lives in services               | Move behavior into the entities and value objects that own the data                           |
| **Oversized Aggregates** | Large clusters with locking/performance issues                            | Shrink boundaries to only what must be immediately consistent                                 |
| **Leaky Layers**         | ORM base classes in domain entities; HTTP details in application services | Enforce the Dependency Rule; use interfaces at layer boundaries                               |
| **Language Drift**       | Code names diverge from what the team says in conversation                | Regular model reviews; rename code to match evolving language                                 |
| **Big Ball of Mud**      | No clear boundaries; models tangled together                              | Draw a boundary around the mess; build clean contexts alongside it with anticorruption layers |

---

## Diagram Guidelines

- Keep diagrams to **4–6 concepts** each. Many small diagrams over one large one.
- Use diagrams to **start conversations**, not to specify.
- Supplement with written descriptions for behavior, constraints, and rules.
- If the code and the diagram disagree, **the code wins**.
- Recommended tools: Mermaid, draw.io, Excalidraw, PlantUML, C4 model.
