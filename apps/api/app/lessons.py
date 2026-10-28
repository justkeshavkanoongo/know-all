from .lesson_models import (
    CommonMistake,
    DialogueTurn,
    LessonConcept,
    LessonDetail,
    LessonDialogue,
    LessonCourseReference,
    LessonGrammar,
    LessonLevelReference,
    LessonObjective,
    LessonSection,
    LessonStep,
    LessonVocabulary,
)


GERMAN_A1_GREETINGS = LessonDetail(
    lesson_id="german-a1-greetings",
    course=LessonCourseReference(id="course-german", slug="german", title="German"),
    level=LessonLevelReference(id="german-a1", title="A1 · Beginner"),
    title="Greetings and introducing yourself",
    review_status="reviewed",
    content_version="1.0.0",
    objectives=(
        LessonObjective(id="greet-politely", description="Choose a greeting for a simple everyday situation."),
        LessonObjective(id="introduce-yourself", description="Give your name and ask another person for theirs."),
        LessonObjective(id="ask-how-someone-is", description="Ask and answer how someone is in a short exchange."),
        LessonObjective(id="close-conversation", description="Use a suitable expression to say goodbye."),
    ),
    vocabulary=(
        LessonVocabulary(term="Hallo", translation="Hello", example="Hallo, ich bin Ada.", example_translation="Hello, I’m Ada.", pronunciation_note="The h is audible; keep the final o clear."),
        LessonVocabulary(term="Guten Morgen", translation="Good morning", example="Guten Morgen, Frau Weber.", example_translation="Good morning, Ms Weber."),
        LessonVocabulary(term="Guten Tag", translation="Good day / hello", example="Guten Tag! Wie heißen Sie?", example_translation="Hello! What is your name?", pronunciation_note="The final g in Tag is pronounced like a k."),
        LessonVocabulary(term="Guten Abend", translation="Good evening", example="Guten Abend, Herr Klein.", example_translation="Good evening, Mr Klein."),
        LessonVocabulary(term="Tschüss", translation="Bye", example="Tschüss, bis morgen!", example_translation="Bye, see you tomorrow!"),
        LessonVocabulary(term="Auf Wiedersehen", translation="Goodbye", example="Auf Wiedersehen, Frau Weber.", example_translation="Goodbye, Ms Weber."),
        LessonVocabulary(term="Wie heißt du?", translation="What is your name? (informal)", example="Hallo! Wie heißt du?", example_translation="Hi! What is your name?"),
        LessonVocabulary(term="Wie heißen Sie?", translation="What is your name? (formal)", example="Guten Tag. Wie heißen Sie?", example_translation="Hello. What is your name?"),
        LessonVocabulary(term="Ich heiße …", translation="My name is …", example="Ich heiße Ada.", example_translation="My name is Ada."),
        LessonVocabulary(term="Wie geht es dir?", translation="How are you? (informal)", example="Wie geht es dir? Gut, danke.", example_translation="How are you? Fine, thanks."),
        LessonVocabulary(term="Wie geht es Ihnen?", translation="How are you? (formal)", example="Wie geht es Ihnen, Herr Klein?", example_translation="How are you, Mr Klein?"),
        LessonVocabulary(term="Gut, danke.", translation="Fine, thank you.", example="Mir geht es gut, danke.", example_translation="I am well, thank you."),
        LessonVocabulary(term="Und dir?", translation="And you? (informal)", example="Gut, danke. Und dir?", example_translation="Fine, thanks. And you?"),
        LessonVocabulary(term="Bitte", translation="Please / you’re welcome", example="Ein Kaffee, bitte.", example_translation="A coffee, please."),
        LessonVocabulary(term="Danke", translation="Thank you", example="Danke, sehr nett.", example_translation="Thank you, very kind."),
    ),
    grammar=(
        LessonGrammar(id="german-ich-heisse", title="Say your name with heißen", explanation="Use ich heiße followed by your name. The verb heißen changes to heißt with du and heißen with Sie.", examples=("Ich heiße Ada.", "Wie heißt du?", "Wie heißen Sie?")),
        LessonGrammar(id="german-formal-informal-address", title="Choose du or Sie", explanation="Use du with friends, children, and people who invite you to use it. Use Sie in formal situations. The formal pronoun is capitalized, and its verb form is heißen.", examples=("Wie heißt du?", "Wie heißen Sie, Frau Weber?")),
        LessonGrammar(id="german-greeting-register", title="Match the greeting to the situation", explanation="Hallo and Tschüss are common informal choices. Guten Morgen, Guten Tag, Guten Abend, and Auf Wiedersehen work well in polite or formal exchanges.", examples=("Hallo, Ben!", "Guten Tag, Frau Weber.")),
        LessonGrammar(id="german-greeting-question-order", title="Ask a simple question", explanation="In a yes-or-no question or a short question beginning with wie, the conjugated verb appears before the subject when the subject is stated.", examples=("Wie heißen Sie?", "Wie geht es Ihnen?")),
    ),
    sections=(
        LessonSection(section_id="choose-a-greeting", title="1. Choose a greeting", introduction="German greetings can show the time of day and how formal a situation feels.", steps=(
            LessonStep(title="Notice the time", explanation="Guten Morgen is used in the morning; Guten Abend is used in the evening. Guten Tag is a useful daytime greeting.", example="Guten Morgen, Frau Weber."),
            LessonStep(title="Notice the relationship", explanation="Hallo is relaxed and widely understood. In a first meeting or formal setting, a time-of-day greeting sounds more polite.", example="Guten Tag, Herr Klein."),
            LessonStep(title="Plan a matching goodbye", explanation="Tschüss is informal. Auf Wiedersehen is a polite choice when you part ways.", example="Auf Wiedersehen, Frau Weber."),
        )),
        LessonSection(section_id="introduce-yourself", title="2. Introduce yourself", introduction="A short introduction can be built from a greeting, a name, and a question for the other person.", steps=(
            LessonStep(title="Start with a greeting", explanation="Choose Hallo for an informal exchange or Guten Tag for a more polite one.", example="Hallo!"),
            LessonStep(title="Give your name", explanation="Use ich heiße and then your name. The letter ß is part of the spelling of heiße.", example="Ich heiße Ada."),
            LessonStep(title="Ask the other person's name", explanation="Use Wie heißt du? informally or Wie heißen Sie? formally.", example="Wie heißen Sie?"),
        )),
        LessonSection(section_id="ask-how-someone-is", title="3. Ask how someone is", introduction="After an introduction, people may ask how the other person is. The question changes with the form of address.", steps=(
            LessonStep(title="Ask informally or formally", explanation="Use dir with du and Ihnen with formal Sie.", example="Wie geht es dir? / Wie geht es Ihnen?"),
            LessonStep(title="Answer briefly", explanation="Gut, danke is a common short answer. Add und dir? or und Ihnen? to ask the question back.", example="Gut, danke. Und dir?"),
        )),
    ),
    dialogues=(
        LessonDialogue(dialogue_id="meeting-ada-ben", title="Two people meet", context="An informal first meeting between two people about the same age.", turns=(
            DialogueTurn(speaker="Ada", text="Hallo! Ich heiße Ada. Wie heißt du?", translation="Hi! My name is Ada. What is your name?"),
            DialogueTurn(speaker="Ben", text="Hallo Ada, ich heiße Ben. Wie geht es dir?", translation="Hi Ada, my name is Ben. How are you?"),
            DialogueTurn(speaker="Ada", text="Gut, danke. Und dir?", translation="Fine, thanks. And you?"),
            DialogueTurn(speaker="Ben", text="Auch gut, danke!", translation="Good too, thanks!"),
        )),
        LessonDialogue(dialogue_id="meeting-ms-weber", title="A polite introduction", context="A learner greets Ms Weber in a formal first meeting.", turns=(
            DialogueTurn(speaker="Learner", text="Guten Tag, Frau Weber. Ich heiße Alex. Wie heißen Sie?", translation="Hello, Ms Weber. My name is Alex. What is your name?"),
            DialogueTurn(speaker="Frau Weber", text="Guten Tag. Ich heiße Anna Weber. Wie geht es Ihnen?", translation="Hello. My name is Anna Weber. How are you?"),
            DialogueTurn(speaker="Learner", text="Gut, danke. Und Ihnen?", translation="Fine, thank you. And you?"),
            DialogueTurn(speaker="Frau Weber", text="Auch gut, danke. Auf Wiedersehen!", translation="Good too, thank you. Goodbye!"),
        )),
    ),
    common_mistakes=(
        CommonMistake(incorrect="Ich bin heiße Ada.", correction="Ich heiße Ada.", explanation="Do not combine bin and heiße. For this beginner introduction, use the single expression ich heiße."),
        CommonMistake(incorrect="Wie heißen du?", correction="Wie heißt du?", explanation="With du, heißen changes to heißt. The formal Sie uses heißen."),
        CommonMistake(incorrect="Wie geht es du?", correction="Wie geht es dir?", explanation="After es geht, use the dative form dir (informal) or Ihnen (formal)."),
        CommonMistake(incorrect="Tschüss, Frau Weber!" , correction="Auf Wiedersehen, Frau Weber!", explanation="Tschüss is informal. In a polite exchange, Auf Wiedersehen is a better fit."),
    ),
    recap=(
        "Use Guten Morgen, Guten Tag, or Guten Abend to fit the time and situation.",
        "Introduce yourself with Ich heiße … and ask Wie heißt du? or Wie heißen Sie?",
        "Match du with heißt and Sie with heißen; formal Sie is capitalized.",
        "Ask Wie geht es dir? informally and Wie geht es Ihnen? formally.",
        "Choose Tschüss for an informal goodbye and Auf Wiedersehen for a polite one.",
    ),
    concepts=(
        LessonConcept(id="german-greetings", title="Greetings and farewells", description="Select greetings and goodbyes appropriate to time and formality."),
        LessonConcept(id="german-self-introduction", title="Names and introductions", description="Give a name and ask another person's name using heißen."),
        LessonConcept(id="german-formal-address", title="Formal and informal address", description="Distinguish du from Sie and use the corresponding verb forms."),
        LessonConcept(id="german-wie-gehts", title="Asking how someone is", description="Ask and respond to a simple question about wellbeing."),
    ),
)

LESSONS: dict[str, LessonDetail] = {GERMAN_A1_GREETINGS.lesson_id: GERMAN_A1_GREETINGS}


def get_lesson(lesson_id: str) -> LessonDetail | None:
    return LESSONS.get(lesson_id)
