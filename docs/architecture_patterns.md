# Practical Foundation

This guide walks you how to design software according to a synthesis of best practices across common architecture design patterns.
It draws from Domain-Driven Design (DDD), Clean Architecture, Hexagonal Architecture, and Onion Architecture — but everything you need to start applying these concepts is here.

This section covers what these ideas are, why they matter, and how to apply them. By the end, you should be able to look at a codebase built on these principles and understand why it's structured the way it is — and make informed decisions when building new features or refactoring existing ones.

---
## 1. The Core Idea

Most software exists to solve a problem in some real-world area of activity — logistics, finance, healthcare, e-commerce, whatever. That area of activity is the **domain**. The central premise of everything in this guide is a single claim:

> **The structure of your software should be driven by the structure of the problem it solves, not by the frameworks or infrastructure it uses.**

This sounds obvious, but in practice it's surprisingly easy to end up with a codebase where the shape of the database, the conventions of a web framework, or the patterns of a particular library dictate how business logic is organized. When that happens, the code becomes harder to change in response to actual business needs — which is the one thing it absolutely must be good at.

The design traditions drawn from — DDD, Clean Architecture, Hexagonal Architecture, Onion Architecture — all converge on this same insight. They disagree on some details, but they share a common backbone:

- **Put business logic at the center.** It should not depend on infrastructure.
- **Push infrastructure to the edges.** Databases, APIs, UIs, and frameworks are details.
- **Use clear boundaries.** Separate things that change for different reasons.
- **Invest in shared language.** The words your team uses to describe the domain should show up in the code.

The rest of this guide unpacks these ideas into things you can actually do.

---
## 2. The Domain

### What It Means

The **domain** is the real-world subject area your software operates in. If you're building software for a logistics company, the domain is logistics — shipments, carriers, routes, delivery windows, customs paperwork. If you're building software for a hospital, the domain is clinical operations — patients, encounters, diagnoses, treatment plans.

The domain is not your code. The domain exists whether your software does or not. Your software's job is to model the domain well enough to be useful.

### Why It's Central

Software that doesn't reflect its domain accurately will fight you at every turn. Requirements changes will feel expensive because the code doesn't map to the concepts being changed. Bugs will cluster around areas where the code's model and the real-world model diverge. New team members will struggle because reading the code doesn't teach them anything about what the system actually does.

Conversely, software that models its domain well tends to be easier to reason about, easier to change, and easier to explain.

### Domain Knowledge Is Built, Not Given

Nobody hands you a finished domain model. You build it through conversation with **domain experts** — the people who understand the business problem deeply. These might be product managers, operations staff, clinicians, or actual end users.

This is an iterative process. You start with a rough, incomplete picture. You talk. You sketch diagrams. You discover that a concept you thought was simple is actually two different concepts. You discover that two concepts you thought were different are actually the same thing viewed from different angles. Each iteration sharpens the model.

**Expect this process to take time.** It is not overhead — it is the design work.

### A Worked Example

Consider a flight monitoring system. Early conversations with air traffic controllers might produce a vague picture: planes take off, follow paths, and land. Through continued discussion, specific concepts emerge:

- A **Route** is the projected ground path a plane follows, composed of a series of **Fixes** (points on Earth's surface defined by latitude and longitude).
- A **Flight Plan** contains the route plus altitude, speed, aircraft type, and crew information.
- What we actually track and measure is a **Flight**, not an aircraft — the aircraft is a physical thing, but the flight is the operational concept that matters for monitoring.

Each of these discoveries refined the model. None of them were obvious at the start. This is how domain knowledge gets built.

---
## 3. Ubiquitous Language

### The Problem

Software teams have a persistent communication problem. Developers talk in terms of classes, methods, patterns, and frameworks. Domain experts talk in terms of their business — routes, registrations, invoices, claims. When these groups work together, they constantly translate between vocabularies, and things get lost in translation.

Even worse, the same word often means different things to different people. "Account" means one thing in billing, another in authentication, and another in CRM. "Status" could be a database field, an enum, a workflow state, or a flag — depending on who's talking.

### The Solution

A **ubiquitous language** is a shared vocabulary, grounded in the domain model, that the entire team commits to using — in conversation, in documents, in code, in tests. It is not the developers' language and not the domain experts' language. It is the **model's** language.

Key properties of a ubiquitous language:

- **It appears in the code.** Class names, method names, and module names should use the same terms the team uses in conversation. If the team says "registration," the code should have a `Registration` class — not a `UserSignupRecord`.
- **It evolves.** When the team discovers that a concept was misnamed or misunderstood, the language changes, and the code changes with it.
- **Domain experts can follow it.** If a domain expert can't understand a description of the model, something is probably wrong with the model.
- **It is scoped.** A ubiquitous language applies within a specific context (more on this in #6. Strategic Design). The same word can mean different things in different contexts, and that's fine — as long as each context is internally consistent.

### How to Build It

Listen carefully to how domain experts describe their work. Pay attention to the nouns (these often become entities or value objects) and the verbs (these often become methods or services). But go deeper than surface-level vocabulary:

- **Watch for hidden concepts.** When a domain expert says "the person has a status of waiting," dig in. Is "status" a real concept, or is it a shorthand for something richer — like a `StandbyRegistration` on a `WaitingList`?
- **Watch for implementation language bleeding in.** If someone says "we send it via the message bus for processing," the message bus is an implementation detail, not a domain concept. What's the actual business operation happening?
- **Watch for contradictions.** When two domain experts describe the same thing differently, that's a signal — either they're talking about different contexts, or the model needs refinement.

When the language changes, refactor the code. Rename classes, methods, and modules to match. This isn't cosmetic — it keeps the code aligned with the team's understanding, which is what makes the code navigable over time.

---
## 4. Layers and Boundaries

This section is where ideas from DDD, Clean Architecture, Hexagonal Architecture, and Onion Architecture converge most visibly. They all advocate separating software into layers based on responsibility, with one critical rule governing how layers relate to each other.

### The Dependency Rule

This is the single most important structural rule in this approach, and it comes directly from Clean Architecture (though every tradition drawn from expresses a version of it):

> **Source code dependencies must point inward — toward the domain.**

The domain layer must not depend on the infrastructure layer. The infrastructure layer may depend on the domain layer. This means the domain layer doesn't know whether data is stored in PostgreSQL or a flat file, whether the UI is a web app or a CLI, or whether messages arrive via HTTP or a queue.

This rule is what makes your business logic testable in isolation, swappable across infrastructure, and resilient to framework changes.

### The Four Layers

Our approach uses four conceptual layers. These map closely to what you'll find in DDD's layered architecture, Clean Architecture's concentric circles, and Hexagonal Architecture's port-and-adapter structure.

```
┌─────────────────────────────────────┐
│         Presentation / UI           │  ← Outermost: user-facing
├─────────────────────────────────────┤
│         Application Layer           │  ← Orchestration, use cases
├─────────────────────────────────────┤
│          Domain Layer               │  ← Business rules, the core
├─────────────────────────────────────┤
│       Infrastructure Layer          │  ← Databases, APIs, frameworks
└─────────────────────────────────────┘

     Dependencies point INWARD (↑)
```

**Domain Layer** — The center of gravity. Contains business rules, domain models (entities, value objects), domain services, and domain events. Has no dependencies on any other layer. This is the code that would survive if you ripped out your database, replaced your web framework, and rewired all your integrations.

**Application Layer** — A thin orchestration layer. Contains use cases (sometimes called application services or interactors). Coordinates workflows by calling into the domain layer and delegating infrastructure concerns outward. Does not contain business logic — it *directs* business logic. Does not hold business object state, though it may track workflow/task state. Think of it as the director of a play: it tells the actors when to go on stage, but it doesn't perform.

**Infrastructure Layer** — Implements the technical capabilities the other layers need: database access, file I/O, external API calls, message queues, email sending. In Hexagonal Architecture terms, this is where **adapters** live — concrete implementations of the **ports** (interfaces) defined by the domain or application layers. The infrastructure layer depends inward on the domain; the domain never depends outward on infrastructure.

**Presentation / UI Layer** — Handles user interaction. Web controllers, CLI handlers, API endpoint definitions, view rendering. Translates between the outside world's format (HTTP requests, command-line arguments) and the application layer's format. In Clean Architecture terms, this is part of the outermost "Frameworks & Drivers" ring.

### How the Layers Interact (A Concrete Example)

A user wants to book a flight route:

1. **Presentation**: An HTTP controller receives the request and extracts the parameters.
2. **Application**: A `BookFlightRoute` use case is called. It fetches the relevant domain objects via a repository interface (defined in the domain, implemented in infrastructure).
3. **Domain**: The `Flight` entity checks security margins against other booked flights. The `Route` value object validates that the fixes form a legal path. Business rules are enforced here.
4. **Infrastructure**: The repository implementation persists the updated `Flight` to the database. A notification adapter sends a confirmation message.

Notice: the domain layer never imports a database library, never constructs an HTTP response, never touches a message queue. It defines interfaces (ports) for what it needs, and the infrastructure layer provides concrete implementations (adapters).

### Why This Matters

This structure gives you several things that compound over time:

- **Testability.** You can unit test domain logic without spinning up a database or a web server. Inject a fake repository, call the use case, assert on the result.
- **Flexibility.** Swapping PostgreSQL for DynamoDB is an infrastructure change. The domain and application layers don't know or care.
- **Readability.** When a new developer opens the domain layer, they see business concepts. When they open the infrastructure layer, they see technical implementations. There's a clear place for everything.
- **Resilience to framework churn.** Frameworks come and go. Your business rules shouldn't be entangled with any of them.

---
## 5. Building Blocks

These are the tactical patterns you'll use day-to-day when implementing the domain layer. They originate from DDD but are used across all the architectural traditions drawn from.

### Entities

An **entity** is an object that has a distinct identity that persists over time. Two entities with the same attributes but different identities are not the same thing.

A `Customer` with ID `C-1234` is a specific customer, even if their name and address change. A `Flight` with flight number `UA-447` is a specific flight, even as its status changes from `scheduled` to `airborne` to `landed`.

Key properties:

- Identity is the defining characteristic, not attributes.
- Entities have lifecycle — they are created, change state, and eventually may be archived or deleted.
- Equality is based on identity, not on attribute values.

Practical guidance: When modeling, ask "do I need to track this thing over time and distinguish it from other things with similar properties?" If yes, it's an entity. If no, it's probably a value object.

### Value Objects

A **value object** is an object defined entirely by its attributes. It has no identity. Two value objects with the same attributes are interchangeable.

A `Money(amount=100, currency="USD")` is equal to another `Money(amount=100, currency="USD")`. An `Address(street="123 Main", city="Portland")` is equal to another address with the same fields.

Key properties:

- Immutable. Once created, a value object doesn't change. If you need different values, create a new instance.
- Equality is based on all attributes.
- No identity tracking overhead. Easy to create, copy, share, and discard.
- A good place to put self-contained computations (e.g., `Money.add(other_money)`).

Practical guidance: Default to value objects when you can. They are simpler, safer, and easier to test than entities. Group related attributes into a value object when they form a conceptual whole — for example, pull `street`, `city`, `state`, `zip` out of a `Customer` entity and into an `Address` value object.

### Aggregates

An **aggregate** is a cluster of entities and value objects that are treated as a single unit for data changes. Every aggregate has a **root entity** — the only object in the aggregate that outside code is allowed to reference directly.

Why this matters: in any nontrivial domain, objects have complex relationships. Without aggregates, you end up with a tangled web where any piece of code can reach in and modify any object, making invariants nearly impossible to enforce and concurrency a nightmare.

Aggregate rules:

- The root entity has a global identity. Internal entities (if any) have local identity only.
- External objects hold references only to the root.
- All changes go through the root. The root enforces invariants for the whole aggregate.
- Deleting the root deletes everything inside the aggregate.
- If you need to pass internal data out, pass copies (value objects), not references.

Practical guidance: Keep aggregates small. A common mistake is making them too large, which creates contention and performance problems. The aggregate boundary should be the smallest group of objects that must be consistent with each other at all times.

### Domain Services

Some operations don't naturally belong to any single entity or value object. Transferring money between two accounts, for example — it doesn't belong to the sending account or the receiving account. Forcing it into either one distorts the model.

A **domain service** is a stateless operation that represents a domain concept. It operates on entities and value objects but doesn't hold state of its own.

Three characteristics of a domain service:

1. The operation it performs is a meaningful domain concept (not a technical utility).
2. The operation involves multiple domain objects.
3. The operation is stateless.

Important distinction: not every service is a domain service. Infrastructure services (sending email, querying a database) live in the infrastructure layer. Application services (orchestrating a use case) live in the application layer. Domain services encapsulate *business logic* that doesn't fit into a single entity or value object.

### Repositories

A **repository** provides the illusion of an in-memory collection of domain objects. It abstracts away persistence — the domain layer asks a repository for an entity by its identity (or by a specification), and gets back a domain object. It doesn't know or care whether that object came from a database, an API, or a file.

Key properties:

- The repository **interface** is defined in the domain layer. It speaks the language of the domain (`find_customer_by_id`, not `execute_sql_query`).
- The repository **implementation** lives in the infrastructure layer. It handles the actual database queries, ORM calls, or API requests.
- Repositories operate on aggregate roots. You don't have a repository for every object — you have a repository for each aggregate root that needs direct access.

This split — interface in the domain, implementation in infrastructure — is a textbook application of the Dependency Rule. The domain defines what it needs (a port), and the infrastructure provides it (an adapter).

### Factories

When creating an object (especially an aggregate) is complex — it involves multiple steps, enforcing invariants, generating identities, or assembling child objects — that creation logic should be extracted into a **factory**.

Factories encapsulate construction knowledge so that client code doesn't need to understand the internal structure of what it's building. This preserves encapsulation and keeps creation atomic: either the whole aggregate is created in a valid state, or creation fails.

Practical guidance: Not every object needs a factory. Use a plain constructor when construction is simple and all necessary attributes are passed directly. Reach for a factory when construction involves conditional logic, invariant enforcement across multiple objects, or identity generation.

### Modules

As a model grows, it needs organizational structure. **Modules** (packages, namespaces — the terminology varies by language) group related concepts to manage complexity.

Good modules have:

- **High cohesion.** The things inside a module are closely related.
- **Low coupling.** Modules interact through well-defined, narrow interfaces.
- **Meaningful names.** Module names should be part of the ubiquitous language. They should tell the story of the system.

Practical guidance: Don't freeze module structure too early. As the model evolves, modules may need to be reorganized. Module-level refactoring is more expensive than class-level refactoring, but ignoring a bad module structure is even more expensive over time.

---
## 6. Strategic Design

The building blocks in Section 5 are **tactical** — they help you write good code within a single model. Strategic design is about the bigger picture: how multiple models coexist in a large system, how teams coordinate, and where to draw boundaries.

### Bounded Contexts

In any nontrivial system, you'll discover that a single unified model for everything doesn't work. The word "account" means different things to the billing team and the identity team. The concept of a "customer" looks different in sales vs. support vs. compliance.

A **bounded context** is an explicit boundary within which a particular model is consistent and the ubiquitous language applies. Inside a bounded context, every term has one meaning. Across bounded contexts, the same term might mean different things — and that's expected.

How to identify bounded contexts:

- **Team boundaries.** If two teams work independently on different parts of the system, they likely operate in different bounded contexts.
- **Linguistic boundaries.** When the same word means different things in different parts of the business, that's a boundary.
- **Conceptual boundaries.** When models diverge — when the `Customer` in one area has attributes and behaviors that are irrelevant in another area — that's a signal.

A bounded context is not a module. A bounded context *contains* modules. It's a higher-level boundary that defines where a model begins and ends.

### Context Maps

A **context map** is a document (diagram, written description, or both) that shows all the bounded contexts in a system and the relationships between them. It answers: how do these contexts communicate? Who depends on whom? Where does translation happen?

You don't need a formal notation. What matters is that everyone on the project can see the big picture and understands the interfaces between contexts.

### Integration Patterns

When two bounded contexts need to interact, the relationship between them falls into one of several patterns:

**Shared Kernel** — Two teams agree to share a small subset of the model. Changes to the shared part require coordination. This demands good communication and discipline. Use sparingly — it creates tight coupling between teams.

**Customer-Supplier** — One context (the supplier/upstream) provides data or services that another context (the customer/downstream) depends on. The supplier team plans its work with the customer's needs in mind. Works well when both teams are under the same management or have aligned incentives.

**Conformist** — Like customer-supplier, but the upstream team has no incentive or ability to accommodate the downstream team. The downstream team simply conforms to whatever the upstream provides. This is pragmatic when the upstream model is good enough and the cost of fighting it exceeds the cost of adapting.

**Anticorruption Layer** — When you need to integrate with an external system (legacy, third-party, or just a context with a very different model) without letting its model infect yours. You build a translation layer that presents the external system in your domain's terms. This is a critical pattern for working with legacy systems.

The anticorruption layer is typically implemented as a combination of:
- A **service** (from the client's perspective, a natural part of its domain)
- A **facade** (simplifies the external system's interface)
- An **adapter** (converts between the two models)
- A **translator** (handles data/object conversion)

**Separate Ways** — Sometimes two parts of a system simply don't need to interact. When integration costs exceed the benefits, keep the contexts fully independent. Before committing to this, make sure you won't need to integrate later — models that evolve independently are expensive to reconnect.

**Open Host Service** — When many contexts need to integrate with yours, define a stable, well-documented protocol (a set of services) that any consumer can use. This avoids building one-off translation layers for every new integration.

### Continuous Integration Within a Context

Inside a single bounded context, continuous integration is essential. Multiple people working in the same context will naturally introduce small inconsistencies — duplicate concepts, contradictory naming, logic in the wrong place. Frequent merges, automated tests, and ongoing conversations about the model counteract this drift.

Continuous integration applies *within* a bounded context. It's not a tool for managing *relationships between* contexts.

---
## 7. Refactoring Toward Deeper Insight

### Continuous Refactoring

A domain model is never finished. It starts rough and incomplete, and it improves through iterative refinement. As the team learns more about the domain — through conversations with experts, through seeing how the code behaves, through discovering edge cases — the model evolves.

This evolution happens through refactoring: redesigning the code to better express the domain without changing observable behavior. Two kinds of refactoring matter here:

- **Technical refactoring** — improving code quality, applying design patterns, cleaning up structure. Well-understood, tool-supported, and usually low-risk.
- **Domain refactoring** — changing the model because you've gained new insight into the domain. Renaming concepts, splitting objects, introducing new abstractions, removing ones that turned out to be wrong. Harder to systematize, higher reward.

Both are necessary. Technical refactoring without domain insight produces clean code that models the wrong thing. Domain insight without technical refactoring produces the right model trapped in code that's painful to work with.

### Making Implicit Concepts Explicit

One of the highest-value refactoring moves is taking something implicit in the code and making it explicit. This often corresponds to a breakthrough in understanding.

Signs that an implicit concept is hiding:

- **The language is a clue.** If the team keeps referring to a concept in conversation that doesn't appear in the code, it's implicit.
- **Awkward code is a clue.** When a section of logic is convoluted or hard to follow, there may be a missing concept whose absence forces other objects to compensate.
- **Contradictions are a clue.** When domain experts seem to disagree, sometimes the resolution reveals a concept that neither one was naming.

Three specific patterns for making concepts explicit:

**Constraints** — When an invariant is buried in a conditional inside a method, extract it into a named method or a dedicated object. Instead of `if content.size() + 1 <= capacity`, write `if is_space_available()`. The logic is the same. The readability and expressiveness are dramatically better.

**Processes** — When a workflow or multi-step procedure exists in the domain, model it explicitly. Use a domain service, and if there are multiple strategies for carrying out the process, use the Strategy pattern to encapsulate the alternatives.

**Specifications** — When complex business rules are used to validate, select, or filter objects, extract them into specification objects. This keeps entities focused on their core lifecycle responsibilities and makes the rules themselves composable, testable, and readable.

### Breakthroughs

Sometimes, a series of small refinements suddenly unlocks a fundamental shift in the model — a **breakthrough**. A concept that was missing clicks into place, and suddenly large sections of the design simplify dramatically.

Breakthroughs are high-value but come with risk: they often require significant refactoring. Budget for this. A codebase designed with flexibility in mind (small aggregates, well-defined boundaries, good test coverage) can absorb breakthroughs without major disruption. A rigid codebase cannot.

---
## 8. Real-World Patterns and Challenges

### Domain Events

Sometimes you need to capture the fact that something happened in the domain — not as a side effect, but as a first-class concept. A `CourseRegistrationPlaced`, an `OrderShipped`, a `PaymentReceived`. These are **domain events**.

Domain events are:

- Immutable (they represent something that already happened)
- Named in past tense (they describe a completed fact)
- Part of the domain model (they are not infrastructure events like "message published to queue")
- Useful for decoupling aggregates that need to react to each other's changes
- Especially valuable in distributed systems, where they can be used to propagate state changes asynchronously

### Distillation and Core Domain

In a large system, not everything is equally important. **Distillation** is the process of identifying the **core domain** — the part of the model that is most central to the business's competitive advantage and value — and separating it from **generic subdomains** (things that are necessary but not unique, like authentication, routing, or currency conversion).

Why this matters:

- Put your best people on the core domain. That's where design quality has the highest ROI.
- Generic subdomains can be handled with off-the-shelf solutions, outsourcing, published models, or simpler in-house implementations.
- Making this distinction explicit prevents the team from investing deep design effort in parts of the system that don't warrant it.

### Big Ball of Mud

Sometimes you inherit a codebase where multiple conceptual models are tangled together with no clear boundaries. This is a **big ball of mud**. The strategic response is to draw a boundary around the mess, treat it as a single (messy) bounded context, and avoid letting its problems spread to new code. Don't try to refactor the ball of mud into clean DDD from the inside — instead, build clean contexts alongside it and use anti-corruption layers to interface with it.

### Common Pitfalls

**Anemic Domain Model** — Entities that are just data holders with getters and setters, where all business logic lives in services. This is the opposite of what a rich domain model looks like. If your entities have no behavior, ask whether the logic that operates on them should move into the entity itself.

**Over-engineering Aggregates** — Making aggregates too large, pulling in objects that don't need transactional consistency with the root. This leads to locking contention, performance problems, and unnecessary coupling. Keep aggregates small.

**Leaky Abstractions in Layers** — When database concerns leak into the domain (e.g., domain entities inheriting from an ORM base class), or when HTTP concerns leak into application services. This erodes the Dependency Rule.

**Ubiquitous Language Drift** — When the team stops maintaining the language, code names diverge from what the team says in meetings, and the model silently decays. This is gradual and hard to notice. Regular model reviews and code-to-language alignment checks help.

---
## 9. Modeling and Diagrams

### Purpose of Diagrams

Diagrams are communication tools, not specifications. A good diagram shows the structure and relationships between a small number of concepts clearly enough that someone new to the context can follow a conversation about them.

Guidelines:

- **Keep diagrams small.** A diagram with 4–6 classes and their relationships is far more useful than one with 40. If the model is large, make many small diagrams, each focused on one aspect.
- **Use them as conversation starters.** Sketch on a whiteboard or in a shared doc, then iterate. The discussion the diagram provokes is more valuable than the diagram itself.
- **Don't rely on them exclusively.** Diagrams are good at showing structure and relationships. They are bad at showing behavior, constraints, and rules. Supplement with written descriptions and, ultimately, code.
- **Expect them to be temporary.** In the early stages of modeling, diagrams change frequently. Hand-drawn or low-fidelity diagrams signal "this is in progress," which is the truth.

### UML as a Tool (Not a Requirement)

UML is fine for quick sketches of class relationships. It becomes counterproductive when it grows to fill an entire wall. If you use UML, keep it informal and focused. A few boxes with names and lines between them, annotated with a sentence or two of explanation, is usually sufficient.

### Code as Model

The most authoritative representation of the model is always the code. Well-named classes, methods, and modules — using the ubiquitous language — are themselves a representation of the model. If the code and a diagram disagree, the code wins (and the diagram should be updated or discarded).

Test code is also a form of modeling. BDD-style scenarios (Given / When / Then) can be an excellent way to express domain rules in a way that domain experts can read and validate.

### Recommended Tools

There is no required toolset. Use whatever lets you iterate quickly:

- Whiteboard / paper for live sessions
- Mermaid (renders in Markdown) for diagrams that live alongside code
- draw.io / Excalidraw for more polished but still lightweight diagrams
- PlantUML if the team prefers text-based diagram generation
- C4 model diagrams for system-level context maps
