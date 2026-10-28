from .models import CourseDetail, CourseLevel, CourseModule, CourseSummary

CURRICULUM_NOTE = "Representative outline only; a complete set of authored lessons is not yet available."


def module(module_id: str, title: str, description: str) -> CourseModule:
    return CourseModule(id=module_id, title=title, description=description)


def level(
    level_id: str,
    label: str,
    title: str,
    description: str,
    *modules: CourseModule,
) -> CourseLevel:
    return CourseLevel(
        id=level_id,
        label=label,
        title=title,
        description=description,
        modules=modules,
    )


COURSES: tuple[CourseDetail, ...] = (
    CourseDetail(
        id="course-german",
        slug="german",
        title="German",
        description="Build practical German from first introductions to confident, nuanced communication.",
        learning_rationale="A language becomes usable when its words, grammar and culture are learned in context. This pathway maps representative topics across the CEFR levels.",
        curriculum_note=CURRICULUM_NOTE,
        levels=(
            level("german-a1", "A1", "Beginner", "Start with everyday words, clear pronunciation guidance and simple exchanges.", module("german-a1-first-words", "First words and introductions", "Greetings, names, numbers and short present-tense sentences.")),
            level("german-a2", "A2", "Elementary", "Talk about familiar routines, plans and experiences with growing independence.", module("german-a2-everyday", "Everyday situations", "Useful phrases for routines, directions, shopping and simple plans.")),
            level("german-b1", "B1", "Intermediate", "Connect ideas and handle common situations at work, while travelling and in daily life.", module("german-b1-connected-speech", "Connected communication", "Narrate experiences, explain plans and connect ideas across a conversation.")),
            level("german-b2", "B2", "Upper intermediate", "Express a position clearly and follow more complex written and spoken material.", module("german-b2-argument", "Nuance and argument", "Support a viewpoint, compare options and understand extended texts.")),
            level("german-c1", "C1", "Advanced", "Use German flexibly for demanding study, professional and cultural contexts.", module("german-c1-register", "Register and precision", "Adapt tone, structure and vocabulary to complex audiences and purposes.")),
            level("german-c2", "C2", "Proficient pathway", "Refine subtle meaning and interpret demanding language with precision.", module("german-c2-interpretation", "Subtle meaning", "Explore implication, idiom and stylistic choice across challenging material.")),
        ),
    ),
    CourseDetail(
        id="course-french",
        slug="french",
        title="French",
        description="Develop French for real conversations, thoughtful reading and confident expression.",
        learning_rationale="Steady progress comes from connecting vocabulary, grammar and culture to meaningful situations. This overview represents a path aligned broadly to CEFR levels.",
        curriculum_note=CURRICULUM_NOTE,
        levels=(
            level("french-a1", "A1", "Beginner", "Begin with introductions, essential expressions and simple exchanges.", module("french-a1-first-words", "First words and introductions", "Greetings, names, numbers and short present-tense sentences.")),
            level("french-a2", "A2", "Elementary", "Describe familiar routines and manage straightforward everyday interactions.", module("french-a2-everyday", "Everyday situations", "Useful phrases for routines, directions, ordering and simple plans.")),
            level("french-b1", "B1", "Intermediate", "Share experiences and opinions across familiar social and practical settings.", module("french-b1-connected-speech", "Connected communication", "Narrate experiences, explain plans and connect ideas across a conversation.")),
            level("french-b2", "B2", "Upper intermediate", "Make a clear case and understand increasingly complex material.", module("french-b2-argument", "Nuance and argument", "Support a viewpoint, compare options and understand extended texts.")),
            level("french-c1", "C1", "Advanced", "Use French fluently and flexibly in academic, professional and cultural contexts.", module("french-c1-register", "Register and precision", "Adapt tone, structure and vocabulary to complex audiences and purposes.")),
            level("french-c2", "C2", "Proficient pathway", "Interpret subtle meaning and communicate with a high degree of precision.", module("french-c2-interpretation", "Subtle meaning", "Explore implication, idiom and stylistic choice across challenging material.")),
        ),
    ),
    CourseDetail(
        id="course-literature",
        slug="literature",
        title="Literature",
        description="Read closely, notice how texts work and build interpretations supported by evidence.",
        learning_rationale="Literature rewards attention to language and multiple defensible readings. A progressive path develops close reading before moving toward comparison and criticism.",
        curriculum_note=CURRICULUM_NOTE,
        levels=(
            level("literature-foundations", "Foundations", "Read with attention", "Practice observing details before forming an interpretation.", module("literature-foundations-close-reading", "Close reading", "Notice word choice, imagery, voice and structure in a short passage."), module("literature-foundations-forms", "Forms and genres", "Recognize how poetry, prose and drama shape a reader's expectations.")),
            level("literature-interpretation", "Intermediate", "Interpret and compare", "Connect textual evidence to themes, context and literary choices.", module("literature-interpretation-devices", "Devices and rhetoric", "Explore metaphor, irony, point of view and rhetorical effect."), module("literature-interpretation-context", "Context and movement", "Relate a work to its historical setting and literary movement.")),
            level("literature-criticism", "Advanced", "Make a critical argument", "Develop nuanced comparisons and evaluate interpretive frameworks.", module("literature-criticism-comparison", "Comparative analysis", "Compare texts through a focused question and evidence-based claims."), module("literature-criticism-approaches", "Critical approaches", "Consider how different critical lenses change the questions we ask.")),
        ),
    ),
    CourseDetail(
        id="course-psychology",
        slug="psychology",
        title="Psychology",
        description="Explore how people think, learn and relate through evidence-aware psychological ideas.",
        learning_rationale="Psychology combines concepts with research. Learning to distinguish evidence, interpretation and limitation helps keep explanations thoughtful and grounded.",
        curriculum_note=CURRICULUM_NOTE,
        levels=(
            level("psychology-foundations", "Foundations", "Understand the field", "Build a clear starting vocabulary and learn how psychological claims are studied.", module("psychology-foundations-intro", "Introduction to psychology", "Survey major questions, perspectives and the role of evidence."), module("psychology-foundations-research", "Research and evidence", "Understand basic study designs, measurement and limitations.")),
            level("psychology-processes", "Intermediate", "Explore mind and behavior", "Connect foundational concepts to memory, learning, emotion and social life.", module("psychology-processes-cognition", "Cognition and learning", "Explore attention, memory and learning through everyday examples."), module("psychology-processes-social", "Emotion and social behavior", "Consider motivation, emotion and social influence.")),
            level("psychology-evaluation", "Advanced", "Evaluate explanations", "Compare theoretical accounts and interpret research with appropriate caution.", module("psychology-evaluation-decisions", "Decision-making", "Analyze cognitive biases and the conditions that shape judgment."), module("psychology-evaluation-theory", "Theories and evidence", "Compare frameworks and assess what research can and cannot establish.")),
        ),
    ),
    CourseDetail(
        id="course-philosophy",
        slug="philosophy",
        title="Philosophy",
        description="Clarify difficult questions, reconstruct arguments and develop reasoned positions of your own.",
        learning_rationale="Philosophy is a practice of careful questioning and argument. A progressive path develops logical clarity while making room for different defensible conclusions.",
        curriculum_note=CURRICULUM_NOTE,
        levels=(
            level("philosophy-foundations", "Foundations", "Ask clear questions", "Learn to identify claims, reasons and assumptions in everyday arguments.", module("philosophy-foundations-logic", "Logic and critical thinking", "Reconstruct a simple argument and distinguish validity from truth."), module("philosophy-foundations-questions", "Big questions", "Meet foundational questions about knowledge, reality and value.")),
            level("philosophy-traditions", "Intermediate", "Compare traditions", "Explore major areas and compare how thinkers approach shared questions.", module("philosophy-traditions-ethics", "Ethics and political thought", "Compare approaches to moral choice, justice and collective life."), module("philosophy-traditions-mind", "Knowledge and mind", "Examine questions about evidence, consciousness and personal identity.")),
            level("philosophy-analysis", "Advanced", "Evaluate arguments", "Develop and assess complex arguments, objections and replies.", module("philosophy-analysis-counterarguments", "Counterarguments", "Identify assumptions, formulate objections and assess replies."), module("philosophy-analysis-positions", "Reasoned positions", "Build a clear position while representing alternatives fairly.")),
        ),
    ),
)


def list_course_summaries() -> tuple[CourseSummary, ...]:
    return tuple(
        CourseSummary(
            id=course.id,
            slug=course.slug,
            title=course.title,
            description=course.description,
            learning_rationale=course.learning_rationale,
            curriculum_note=course.curriculum_note,
            level_count=len(course.levels),
            module_count=sum(len(level.modules) for level in course.levels),
        )
        for course in COURSES
    )


def get_course_by_slug(slug: str) -> CourseDetail | None:
    return next((course for course in COURSES if course.slug == slug), None)
