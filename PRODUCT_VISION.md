# Fight IQ AI — The Intelligent Future of Combat Sports

**Your Technique. Perfected by AI.**

## Product vision

This is the product's guiding vision, supplied by its founder. It describes the intended destination, not a claim that every capability is available or validated today. The headline is an aspirational brand statement, not a guarantee of perfect technique or results.

Fight IQ AI is an advanced artificial intelligence platform designed to revolutionize how martial artists train, analyze performance, develop strategies, and improve their fighting intelligence.

Combining computer vision, machine learning, tactical analysis, and personalized AI coaching, Fight IQ aims to transform ordinary training footage into detailed, actionable performance intelligence.

The platform is being designed for practitioners of boxing, mixed martial arts, Muay Thai, Brazilian Jiu-Jitsu, Taekwondo, and other combat disciplines, from beginners developing their fundamentals to professional fighters seeking competitive advantages.

Through video analysis and its proprietary Fight IQ evaluation framework, the system is designed to identify technical weaknesses, defensive vulnerabilities, movement inefficiencies, strategic patterns, and areas for tactical improvement.

Rather than simply telling athletes what they are doing wrong, Fight IQ aims to explain why mistakes occur, how they affect performance, and what specific training interventions can help correct them.

Its adaptive coaching system is envisioned to create individualized development plans based on each fighter's strengths, weaknesses, experience, fighting style, and performance history. A structured decision-tree engine will help athletes understand tactical situations, anticipate possible reactions, and build more complete offensive and defensive systems.

Future capabilities include real-time training analysis, opponent scouting, professional fighter style studies, advanced performance dashboards, and collaborative coaching tools for gyms and academies.

At its core, Fight IQ is built around one fundamental objective: **making high-quality combat sports intelligence, education, and performance analysis more accessible, personalized, and measurable.**

The ultimate vision is to establish Fight IQ as the leading intelligence infrastructure for combat sports—a unified ecosystem connecting athletes, coaches, gyms, and professional organizations through advanced technology and evidence-based training.

**Fight IQ AI — Train with intelligence. Fight with purpose. Evolve with every session.**

## What this means for product decisions

The core training loop is: **capture → inspect evidence → understand a decision → practice a correction → reassess in a later session**.

Every personalized recommendation should answer:

1. What was visible, and where in the footage can the athlete verify it?
2. Why might it matter under this discipline's rules and this athlete's goal?
3. What is observed, what is a hypothesis, and what remains uncertain?
4. What specific adjustment or practice task should the athlete try?
5. What observable result would indicate improvement next time?

Optimize for useful, verifiable coaching and learning over more elaborate scores or longer AI responses. Do not infer intent, causes, or precise biomechanics from evidence that cannot support them. Athlete and coach corrections should be able to improve future plans.

The Fight IQ framework currently organizes manually reviewed observations into distance intelligence, threat recognition, risk management, tactical adaptation, efficiency, and composure. Its weights and scores remain provisional. The proprietary-framework aspiration does not imply validated predictive accuracy, a trained proprietary model, patents, or a reliable ranking of fighters.

## Current baseline

As of v0.3.0, the beta provides local recording/import controls, approximate frame stepping, short-section sampled-image reviews, timestamped evidence, suggested corrections and skills, practice blocks, and manual six-pillar session reviews. Available discipline choices are MMA, boxing, Muay Thai, kickboxing, Brazilian Jiu-Jitsu, and wrestling. Taekwondo is planned.

AI reviews sample five frames per second over a selected section of up to ten seconds. They do not inspect every original frame or continuously analyze a full round. The app currently uses a hosted vision model, not a proprietary motion-analysis model. Athlete profiles, durable history, adaptive longitudinal plans, a decision-tree engine, real-time analysis, scouting, and gym collaboration are not implemented.

The release passed 52 automated tests, deployment checks, and a synthetic blank-image abstention check. Browser media/camera workflows and coaching accuracy on real athlete footage remain unverified. Automated application tests are not evidence of coaching effectiveness.

See [the development roadmap](ROADMAP.md) for the sequence and completion criteria, and [the README](README.md) for current operation and limitations.
