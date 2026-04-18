# Design Influences

### Domain-Driven Design (DDD)

**Origin:** Eric Evans, *Domain-Driven Design: Tackling Complexity in the Heart of Software* (2003).

**Core contribution to the approach:** DDD provides the *vocabulary and modeling philosophy* that forms the backbone of how to talk about and structure business logic. Nearly all of the tactical building blocks — Entities, Value Objects, Aggregates, Repositories, Factories, Domain Services, Modules — come directly from DDD. So does the concept of Ubiquitous Language, Bounded Contexts, Context Maps, and the full suite of strategic integration patterns (Shared Kernel, Anti-corruption Layer, Customer-Supplier, etc.).

**What DDD emphasizes that others don't:** DDD places uniquely heavy emphasis on the *collaborative process* between developers and domain experts. It treats modeling as an ongoing conversation, not a one-time design phase. It also provides the richest treatment of strategic design — how to manage multiple models in a large organization.

**Where to lean on DDD most:** Tactical patterns, ubiquitous language, strategic design, and the fundamental principle that the domain is the center of the software.

### Clean Architecture

**Origin:** Robert C. Martin ("Uncle Bob"), *The Clean Architecture* (2012 blog post; expanded in *Clean Architecture: A Craftsman's Guide to Software Structure and Design*, 2017).

**Core contribution to the approach:** Clean Architecture gives us the **Dependency Rule** — the explicit, directional rule that source code dependencies must always point inward toward the domain. While DDD and the other traditions imply this, Clean Architecture states it as a hard structural constraint and provides concrete guidance on how to enforce it (dependency inversion, interface boundaries, data transfer across layers).

Clean Architecture also provides the clearest articulation of why layers exist: each ring in the concentric model represents a different **level of policy**. Inner rings are high-level policy (business rules). Outer rings are low-level detail (frameworks, UI, databases). The further in, the more abstract and stable. The further out, the more concrete and volatile.

**What Clean Architecture emphasizes that others don't:** A strong focus on making the architecture **framework-independent**. The explicit stance that databases, web frameworks, and UIs are *details* that belong in the outermost ring. Also a clear treatment of what data should look like when crossing layer boundaries (simple data structures, not entities or ORM objects).

**Where to lean on Clean Architecture most:** The Dependency Rule, the principle that frameworks are details, and the guidance on data crossing boundaries.

### Hexagonal Architecture (Ports and Adapters)

**Origin:** Alistair Cockburn (2005). Also adopted and refined by Steve Freeman and Nat Pryce in *Growing Object-Oriented Software, Guided by Tests*.

**Core contribution to the approach:** Hexagonal Architecture gives us the **Ports and Adapters** metaphor, which is the most intuitive mental model for how the domain layer interacts with the outside world. A **port** is an interface defined by the domain (e.g., a repository interface, a notification interface). An **adapter** is a concrete implementation provided by the infrastructure (e.g., a PostgreSQL repository, an email notification sender).

This metaphor is what makes this repository pattern click: the interface is the port (domain layer), the implementation is the adapter (infrastructure layer).

**What Hexagonal Architecture emphasizes that others don't:** Symmetry between the "driving" side (things that call into the application — UI, tests, API consumers) and the "driven" side (things the application calls out to — databases, external services). Both sides connect through ports and adapters.

**Where to lean on Hexagonal Architecture most:** The ports-and-adapters pattern for repository and infrastructure interfaces. The mental model of the domain as something that can be "driven" by any input mechanism and can "drive" any output mechanism.

### Onion Architecture

**Origin:** Jeffrey Palermo (2008).

**Core contribution to the approach:** Onion Architecture is essentially a concentric-layer view (similar to Clean Architecture) with a strong emphasis on the domain at the center and infrastructure at the outermost layer. Its contribution is largely reinforcing — it independently arrived at many of the same conclusions as Clean Architecture, which gives us confidence that these principles are robust.

**What Onion Architecture emphasizes that others don't:** A particularly explicit treatment of the relationship between the Application layer and the Domain layer, and the rule that the Application layer orchestrates but does not contain business logic.

**Where to lean on Onion Architecture most:** The layering model and the clear separation between application orchestration and domain logic.

---
## Where They All Agree

These traditions converge on several fundamental points. This is the foundation the approach rests on:

| Principle                                                                 | DDD | Clean | Hexagonal | Onion |
|---------------------------------------------------------------------------|-----|-------|-----------|-------|
| Business logic belongs at the center, free of infrastructure dependencies | ✓   | ✓     | ✓         | ✓     |
| Infrastructure and frameworks are details that live at the edges          | ✓   | ✓     | ✓         | ✓     |
| Dependencies point inward (domain depends on nothing external)            | ✓   | ✓     | ✓         | ✓     |
| Separation into distinct layers with clear responsibilities               | ✓   | ✓     | ✓         | ✓     |
| Use interfaces/ports to decouple domain from infrastructure               | ✓   | ✓     | ✓         | ✓     |
| Testability of business logic without infrastructure                      | ✓   | ✓     | ✓         | ✓     |

When four independently developed traditions agree on something, it's reasonable to treat that something as a well-established principle rather than an opinion.

---
## Where They Diverge (And Preferred Choices)

### Tactical Modeling Patterns

**DDD** provides a rich set (Entities, Value Objects, Aggregates, etc.). The other three traditions are largely silent on *how* to model the domain internally — they focus on *how to structure the system around the domain*.

**Choice:** Use DDD's tactical patterns. They're the most developed toolkit for structuring domain logic, and nothing in the other traditions contradicts them.

### Layer Naming and Count

**DDD** traditionally names four layers: UI, Application, Domain, Infrastructure. **Clean Architecture** uses four concentric rings: Entities, Use Cases, Interface Adapters, Frameworks & Drivers. **Hexagonal** doesn't prescribe layers — it uses the inside/outside distinction with ports and adapters. **Onion** uses concentric layers similar to Clean.

**Choice:** Use four named layers (Presentation, Application, Domain, Infrastructure) that align with DDD's names but incorporate Clean Architecture's Dependency Rule as the governing structural principle.  Use Hexagonal's ports-and-adapters metaphor for how interfaces connect layers — especially at the domain/infrastructure boundary.

### Strategic Design

**DDD** has a fully developed strategic design toolkit (Bounded Contexts, Context Maps, integration patterns). The others don't address this at all — they're focused on single-application architecture.

**Choice:** Use DDD's strategic design wholesale. Nothing in the other traditions offers a comparable alternative, and it addresses a problem they don't: how to manage multiple models and teams in a large system.

### Framework Stance

**Clean Architecture** takes the strongest position here: frameworks are details and should be kept in the outermost ring. **DDD** is less prescriptive about framework usage. **Hexagonal** is framework-agnostic by design.

**Choice:** Follow Clean Architecture's stance. Frameworks are useful tools, but they should not dictate the structure of the domain. Domain code should be framework-free.

---
## Summary: What Comes From Where

| Concept                                                    | Primary Source                               |
|------------------------------------------------------------|----------------------------------------------|
| Ubiquitous Language                                        | DDD                                          |
| Entities, Value Objects, Aggregates                        | DDD                                          |
| Domain Services                                            | DDD                                          |
| Repositories (concept and aggregate-root scoping)          | DDD                                          |
| Factories                                                  | DDD                                          |
| Modules                                                    | DDD                                          |
| Bounded Contexts and Context Maps                          | DDD                                          |
| Integration Patterns (Shared Kernel, ACL, etc.)            | DDD                                          |
| Domain Events                                              | DDD (later additions and community practice) |
| Distillation / Core Domain                                 | DDD                                          |
| The Dependency Rule                                        | Clean Architecture                           |
| Frameworks are details                                     | Clean Architecture                           |
| Data crossing boundaries as simple structures              | Clean Architecture                           |
| Ports and Adapters (interface/implementation split)        | Hexagonal Architecture                       |
| Four-layer model with domain at center                     | DDD + Onion Architecture                     |
| Application layer orchestrates but holds no business logic | Onion Architecture + DDD                     |

---
## Sources

- **DDD:** 
	- Eric Evans, *Domain-Driven Design: Tackling Complexity in the Heart of Software* (2003). The definitive text. 
	- *Domain-Driven Design Quickly* (InfoQ). A condensed summary.
- **Clean Architecture:** 
	- Robert C. Martin, [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) (2012 blog post). The blog post is short, clear, and covers the essentials. 
	- The 2017 book expands on it significantly.
- **Hexagonal Architecture:** 
	- Alistair Cockburn, [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) (2005).
	- Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests* for a practical application.
- **Onion Architecture:** Jeffrey Palermo, [The Onion Architecture](https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/) (2008 blog series).

---
---
