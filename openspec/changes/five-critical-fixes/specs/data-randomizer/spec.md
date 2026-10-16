## ADDED Requirements

### Requirement: Randomized barrier types per student

The data randomizer SHALL assign each student a unique barrier distribution where three values (concept, reading, expression) sum to 1.0 with at least 0.15 variance between the highest and lowest value.

#### Scenario: Students have different dominant barriers
- **WHEN** randomizer runs on 66 students
- **THEN** at least 15 students have concept as dominant, 15 have reading as dominant, and 15 have expression as dominant

### Requirement: Randomized exercise counts

Each student SHALL receive a randomly assigned `exercises_completed` count between 0 and 50.

#### Scenario: Varied exercise counts
- **WHEN** randomizer runs
- **THEN** exercise counts vary across students with standard deviation > 10

### Requirement: Simulated answer history

Each student SHALL receive 7-30 days of simulated answer records with correctness rates varying between 40% and 95%.

#### Scenario: Diverse performance levels
- **WHEN** randomizer runs
- **THEN** some students have <50% accuracy, some 50-70%, some >70%

### Requirement: Safety check

The randomizer SHALL skip students who already have answer records unless `--force` flag is passed.

#### Scenario: Existing data protected
- **WHEN** randomizer runs without --force on students with existing answers
- **THEN** those students are skipped and a warning is printed
