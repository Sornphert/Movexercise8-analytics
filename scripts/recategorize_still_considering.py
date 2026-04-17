import csv
import re
import shutil

import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "objections.csv")
DST_COPIES = [
    SRC,
    "/Users/sornphert/Downloads/objections_full.csv",
]

# Keyed by normalized phone (digits only, starting with 60)
# Value: (category, primary_objection, child_issue, child_age, notes)
OVERRIDES = {
    "60126011971": ("Still Considering", "Pending — awaiting response after pricing", "Meltdowns, repetitions", "N/S", "'May God bless you.' Got program breakdown. Pending."),
    "60124787332": ("Went Silent", "Went silent — payment link issues, very few replies", "Not stated", "N/S", "HSBC card. Payment link issues. Very few replies."),
    "60165256226": ("Went Silent", "Asked about monthly payment, never replied", "Not stated", "N/S", "Asked about monthly payment. Never replied to options."),
    "60122540043": ("Still Considering", "No clear objection — conversation still open", "8yo son cheating/dishonest. Husband strict ('garang')", "8", "Asked about son's cheating in Zoom. Husband is strict. No price discussed yet."),
    # Unknown lead has no phone — matched by notes prefix
    "__unknown__": ("Not Ready / Timing", "Weekend work conflict — can't attend", "Not stated", "N/S", "Asked about schedule, worried about weekend work conflict. Received ebook."),
    "60162013228": ("Not Ready / Timing", "Time commitment concern — went silent after Day 2", "Not stated", "N/S", "Very engaged Day 1, asked to sign up. Went silent after Day 2 + ebook. Time concern."),
    "60162216632": ("Still Considering", "Still gathering info — no clear objection", "Not stated", "N/S", "Admin-focused (dates, group confusion). Asked for hand/eye video. No objection surfaced."),
    "60143245660": ("Still Considering", "Actively scheduling 1-to-1 consultation with Daphnie", "Not stated", "N/S", "Submitted screening form. Scheduling 1-to-1, needs to apply leave. Wants morning slot."),
    "60103790865": ("Went Silent", "No engagement — 8 msgs, no substantive content", "Not stated", "N/S", "(8 msgs) No substantive exchange."),
    "60105748680": ("Went Silent", "Asked to switch to business number, no follow-up", "Not stated", "N/S", "'Hi, please add me on my business number instead of private number' (12 msgs)"),
    "601110584628": ("Went Silent", "Only asked about ebook, 2 msgs", "Not stated", "N/S", "'I joined the webinar but did not receive my free copy of book.' (2 msgs)"),
    "601128801120": ("Went Silent", "Auto-reply from business (Eastupia), not a lead", "Not stated", "N/S", "Auto-reply: 'Thank you for contacting Eastupia.' Not a real conversation."),
    "601151188753": ("Went Silent", "Only reported ebook link error, no purchase discussion", "Not stated", "N/S", "'Hi Leon, I can't access the free e-book link' (6 msgs)"),
    "601160642523": ("Financial Constraint", "Asked about instalment plan — financial concern", "Not stated", "N/S", "'Please can I find out on the installment plan Please' (8 msgs). Went silent after."),
    "60122325860": ("Other", "Referring a friend, not a buyer themselves", "Not stated", "N/S", "'Plse add my friend Nurul 0137543715' — lead is a referrer, not a buyer."),
    "60122723127": ("Went Silent", "No substantive content — 10 msgs, no notes", "Not stated", "N/S", "(10 msgs) No substantive exchange."),
    "60122880301": ("Went Silent", "Only asked about webinar logistics, no purchase intent", "Not stated", "N/S", "'Tomorrow session is similar or different focus?' (6 msgs)"),
    "60122921460": ("Not Ready / Timing", "Not now — registered for AI courses, needs to focus", "Focus issues", "N/S", "'Not now but probably in future. I have registered for several AI courses.' (14 msgs)"),
    "60122939510": ("Financial Constraint", "Financial — adjusting spending as ECCE teacher trainer", "Not stated", "N/S", "'Still adjust my spending money and yet have suitable time' (22 msgs)"),
    "60123000744": ("Still Considering", "Actively going through online session — 20 msgs", "Not stated", "N/S", "'Hi Leon its ok let me go thru the online session' (20 msgs). Ongoing."),
    "60123174956": ("Not Ready / Timing", "Personal circumstances — attended funeral", "Not stated", "N/S", "'Was attended my friend's bil funeral today' (10 msgs). Personal timing issue."),
    "60123408455": ("Not Ready / Timing", "Son very unwell — doctors can't find reason yet", "Son frequently sick (reason unknown)", "N/S", "'My son is actually not very healthy.. doctors are still looking into it.' (18 msgs)"),
    "60123442362": ("Went Silent", "No substantive content — 8 msgs, no notes", "Not stated", "N/S", "(8 msgs) No substantive exchange."),
    "60123451890": ("Skepticism", "First time encountering method — needs time to process", "Not stated", "N/S", "'It's the 1st time i came across this method.' (22 msgs). Researching."),
    "60123756374": ("Went Silent", "Said would ask questions tomorrow — never followed up", "Not stated", "N/S", "'I have questions to ask but I keep it tomorrow ya.' (8 msgs). Didn't return."),
    "60123772166": ("Not Ready / Timing", "Polite closing — thanked team, not buying", "Not stated", "N/S", "'Thanks for organizing the amazing webinar and assistance throughout!' (17 msgs)"),
    "60123871682": ("Went Silent", "Only reported ebook download error, no purchase intent", "Not stated", "N/S", "'I've submitted the form to claim for the ebook but it failed to download' (6 msgs)"),
    "60124611488": ("Went Silent", "Only 2 msgs, no substantive content", "Not stated", "N/S", "(2 msgs) No substantive exchange."),
    "60124614357": ("Other", "Institution wanting teacher training, not a parent buyer", "Not stated", "N/A", "'We're interested to do training for our teachers' (18 msgs). TTT inquiry."),
    "60124748825": ("Not Ready / Timing", "Low urgency — 'don't have a high level of need'", "Not stated", "N/S", "'I don't have a high level of need' (18 msgs). No compelling reason to join now."),
    "60125080501": ("Other", "Grandma watching out of curiosity — not target buyer", "Not stated", "N/A", "'I would not be joining as i am a grandmother. Followed out of curiosity.' (14 msgs)"),
    "60125619980": ("Other", "Appears to have already purchased VIP", "Not stated", "N/S", "'Hi dapnie. Ive purchase for the vip.my name is farah.' (26 msgs)."),
    "60125655621": ("Went Silent", "Just asked what programs exist, 4 msgs, no follow-up", "Focus (daughter)", "N/S", "'I'm looking for my daughter focus on study.. what are programs available?' (4 msgs)"),
    "60126122133": ("Went Silent", "No substantive content — 4 msgs, no notes", "Not stated", "N/S", "(4 msgs) No substantive exchange."),
    "60126532607": ("Went Silent", "Described problem only, 4 msgs, no purchase discussion", "Focus (child at school)", "N/S", "'Not focusing in class. Short attention span easily distracted' (4 msgs)"),
    "60126575990": ("Not Ready / Timing", "Left session early, asked for recording — timing issue", "Not stated", "N/S", "'I have to go mid way of the live session, is it possible to share the recording?' (14 msgs)"),
    "60126606441": ("Went Silent", "Instagram inquiry, 6 msgs, likely went silent after info", "Not stated", "N/S", "'hi there i saw your add in instagram' (6 msgs)"),
    "60127092800": ("Skepticism", "Questioning if program suits secondary school child", "Child not progressing at secondary school", "N/S", "'I thought it's a mental development program, my child just not progressing in secondary.'"),
    "60128381610": ("Went Silent", "Only wanted ebook, 10 msgs, no purchase discussion", "Not stated", "N/S", "'Hi Leon, can I get the ebook? Thank you' (10 msgs)"),
    "60128851896": ("Spouse Buy-in", "Needs daughter-in-law's confirmation before paying", "Not stated", "N/S", "'My daughter in law is away. Will transfer after I get her confirmation by Tue.' (2 msgs)"),
    "60129071988": ("Went Silent", "Only confirmed ebook delivery, 4 msgs", "Not stated", "N/S", "'Just wanted to confirm, we will receive the ebook via email?' (4 msgs)"),
    "60129093073": ("Not Ready / Timing", "Deferring — 'will take a rain check for now'", "Not stated", "N/S", "'We will take a rain check for now.' (10 msgs)"),
    "60129161364": ("Skepticism", "Questioning what they get from the 1-year course", "Not stated", "N/S", "'what we will get from the one year course?' Needs convincing before deciding."),
    "60129780929": ("Went Silent", "Complained ebook not received weeks later, 10 msgs", "Not stated", "N/S", "'hi i attended the event weeks ago, til today i did not receive my ebook' (10 msgs)"),
    "60133895048": ("Went Silent", "Only asked for session notes via email, 22 msgs", "Not stated", "N/S", "'Can I get your notes in my email address please.Tq' (22 msgs)"),
    "60133938730": ("Went Silent", "Auto-reply ('Thank you for contacting Lily'), not a real lead", "Not stated", "N/S", "Auto-reply: 'Thank you for contacting Lily. Please let me know how I can help you.'"),
    "60135873536": ("Went Silent", "No substantive content — 6 msgs, no notes", "Not stated", "N/S", "(6 msgs) No substantive exchange."),
    "601165692710": ("Still Considering", "High engagement (40 msgs) — ongoing Q&A, no clear objection", "Not stated", "N/S", "'Upcoming Q&A: Submit Your Questions' (40 msgs). Active, no objection surfaced."),
    "60138158228": ("Not Ready / Timing", "Needs more time to think about it", "Not stated", "N/S", "'Thanks for the reply. But I need some times to think about it.' (6 msgs)"),
    "60139277088": ("Went Silent", "No substantive content — 8 msgs, no notes", "Not stated", "N/S", "(8 msgs) No substantive exchange."),
    "60143300962": ("Went Silent", "Only asked about ebook, 8 msgs", "Not stated", "N/S", "'Is this the free e book for attending the both 2 days course?' (8 msgs)"),
    "60143591343": ("Went Silent", "Only 2 msgs — described granddaughter issue, no purchase discussion", "Granddaughter: fiery temper, rebellious", "N/S", "'I'm having problem with my granddaughter. She has a fiery temper, is rebellious.' (2 msgs)"),
    "60146001925": ("Not Ready / Timing", "Sick, missed Day 2 — asked for recording", "Not stated", "N/S", "'Today day 2 im not able to join.. im not feeling well.. when can i get the recording?' (4 msgs)"),
    "60146691826": ("Went Silent", "Only asked about free course, 4 msgs", "Not stated", "N/S", "'Hi I would like to join the free course.' (4 msgs)"),
    "60149312007": ("Went Silent", "Only asked what time the webinar is, 10 msgs", "Not stated", "N/S", "'Hi. May i know what time is the webinar. I have registered' (10 msgs)"),
    "60162126114": ("Skepticism", "Questioning what program is — asked if it includes yoga", "Not stated", "N/S", "'Hi Leon, is movexercise part of yoga exercises too?' (6 msgs). Unclear on method."),
    "60162265020": ("Went Silent", "File error technical issue, 14 msgs — admin only", "Not stated", "N/S", "'It seems the files have error, unable to load' (14 msgs)"),
    "60162666614": ("Went Silent", "Only reported missing Zoom invite, 2 msgs", "Not stated", "N/S", "'Hi I've not received the zoom invite via email yet' (2 msgs)"),
    "60162706610": ("Went Silent", "Described need only, 4 msgs, no purchase discussion", "Focus/attention (child)", "N/S", "'Improve his focus and attention..' (4 msgs). No follow-up."),
    "60163036379": ("Not Ready / Timing", "Not at the moment", "Focus (child)", "N/S", "'Yes im aware but maybe not at the moment but thank you' (6 msgs)"),
    "60163691282": ("Not Ready / Timing", "Explicitly declined — 'No. Not now.'", "Not stated", "N/S", "'No. Not now. Thank you for your 2 days talk/course.' (4 msgs)"),
    "60163831334": ("Financial Constraint", "Asked about cost — went silent after pricing", "Not stated", "N/S", "'May i know The cost / fees for The classes' (10 msgs). Went silent after pricing."),
    "60164217669": ("Not Ready / Timing", "Polite closing — inspired but not buying", "Not stated", "N/S", "'Thank you Leon and Daphne also. It was inspiring stories' (12 msgs)"),
    "60166140031": ("Went Silent", "Only registered for free trial, 2 msgs", "Not stated", "N/S", "'Hi, I have registered for the free trial class for my daughter.' (2 msgs)"),
    "60166239656": ("Went Silent", "No substantive content — 6 msgs, no notes", "Not stated", "N/S", "(6 msgs) No substantive exchange."),
    "60166872402": ("Not Ready / Timing", "Polite closing — 'thank you very much'", "Not stated", "N/S", "'Alright ..thank you very much' (10 msgs). Polite close."),
    "60166876064": ("Went Silent", "Confused about event dates — 16 msgs admin logistics", "Not stated", "N/S", "'Hi.. I am confuse.. in the email it mentioned that the event is on 16-17..' (16 msgs)"),
    "60167253909": ("Prefers Physical", "Wants local option — schools in Johor/Melaka area", "Not stated", "N/S", "'Most of the school at Johor Melaka' — wants physical/local option near them."),
    "60167288803": ("Other", "Already enrolled in another program (Brain Rewiring System)", "Not stated", "N/S", "'I already submitted for Brain rewiring system..' (8 msgs). Not a new buyer."),
    "60168827913": ("Went Silent", "Only asked about participation certificate, 10 msgs", "Not stated", "N/S", "'ok..is there any certificate of participation?' (10 msgs)"),
    "60169191509": ("Went Silent", "No substantive content — 12 msgs, no notes", "Not stated", "N/S", "(12 msgs) No substantive exchange."),
    "60172579693": ("Not Ready / Timing", "Busy — had to go out that night", "Not stated", "N/S", "'Yes I need to go out that night' (8 msgs). Could not commit that evening."),
    "60172873216": ("Went Silent", "Only wanted to redeem ebook, 8 msgs", "Not stated", "N/S", "'Morning Leon. Can I redeem the ebook? Thanks' (8 msgs)"),
    "60175571283": ("Financial Constraint", "Asked about price — financial concern", "Not stated", "N/S", "'But I want to know if the course is how much' (4 msgs). Price sensitivity."),
    "60176541766": ("Went Silent", "Only asked to be added to group, 8 msgs", "Not stated", "N/S", "'Yes please address me into the group' (8 msgs). No purchase discussion."),
    "60177772829": ("Went Silent", "Instagram inquiry — wanted to know more, 8 msgs", "Not stated", "N/S", "'I saw the video in insta about children what is this about want to know more' (8 msgs)"),
    "60179832773": ("Not Ready / Timing", "Self-identified as retiree — not urgently committed", "Not stated", "N/S", "'Still considering. Am a retiree' (6 msgs). Low urgency."),
    "60182603526": ("Went Silent", "No substantive content — 8 msgs, no notes", "Not stated", "N/S", "(8 msgs) No substantive exchange."),
    "60183562628": ("Not Ready / Timing", "Had urgent school matter, had to leave the talk", "Not stated", "N/S", "'I have to leave the Talk. I need to do something for school, urgent.' (20 msgs)"),
    "60183882898": ("Went Silent", "Only asked about class timing, 6 msgs", "Not stated", "N/S", "'When is the online class and timing ya?' (6 msgs)"),
    "60183927077": ("Went Silent", "Only 2 msgs — asked one question about program format", "Not stated", "N/S", "'Can I knw more about the programme? I have to perform at home myself?' (2 msgs)"),
    "60189468641": ("Went Silent", "Only asked about ebook registration repeatedly, 16 msgs", "Focus (child)", "N/S", "'Free e-book must always register again?' (16 msgs). Admin only."),
    "60192396889": ("Went Silent", "Only asked how to get ebook, 4 msgs", "Not stated", "N/S", "'Hi, may I know how do we get the free e-book?' (4 msgs)"),
    "60192643421": ("Financial Constraint", "Asked about tax deductibility — financially motivated", "Not stated", "N/S", "'May i know this program will fall under which item of tax deductible?' (10 msgs)"),
    "60192776639": ("Not Ready / Timing", "Busy at work, couldn't join the session", "Not stated", "N/S", "'i am working now, cannot join wor' (16 msgs). Timing/work conflict."),
    "60193022812": ("Went Silent", "Missed session, 4 msgs, no purchase follow-up", "Not stated", "N/S", "'Hi I missed yesterday's session' (4 msgs)"),
    "60193249511": ("Not Ready / Timing", "Engaged with webinar VIP but didn't commit to main program", "Not stated", "N/S", "'Hi how do i upgrade to vip the rm68?' (14 msgs). Active but didn't convert."),
    "60195287660": ("Not Ready / Timing", "Sunday scheduling conflict — Sunday is school day in the north", "Not stated", "N/S", "'We are from north Sunday is school' (10 msgs). Can't attend on Sundays."),
    "60195512852": ("Not Ready / Timing", "Can't commit to 1-year program", "Not stated", "N/S", "'This is regarding 1yr program right? If yes, im sorry, im not able to commit' (4 msgs)"),
    "60195667392": ("Other", "Already purchased a recording package — existing customer", "Not stated", "N/S", "'i bought package that comes together with recording' (14 msgs). Existing buyer."),
    "60195787293": ("Not Ready / Timing", "Afraid can't commit every weekend 10am-5pm", "Screen addiction", "N/S", "'Afraid I can't commit every weekend 10am-5pm' (24 msgs). Time commitment concern."),
    "60196699544": ("Went Silent", "Described daughter's focus issue, 8 msgs, no purchase", "Focus (daughter, studies)", "N/S", "'I need help with my daughter to concentrate in her studies' (8 msgs)"),
    "60196888664": ("Went Silent", "No substantive content — 14 msgs, no notes", "Not stated", "N/S", "(14 msgs) No substantive exchange."),
    "60197353337": ("Skepticism", "Wants 1-on-1 online session — group format doesn't suit", "Not stated", "N/S", "'Hi! I would like to find out, do you have an online personal session?' (4 msgs)"),
    "60197732119": ("Other", "Educator joining for students, not own child — not target buyer", "Not stated", "N/A", "'Nope. I'm joining for my students not my own child.' (4 msgs)"),
    "60198580288": ("Not Ready / Timing", "Not yet decided — politely declining for now", "Not stated", "N/S", "'For now i not yet decide to join. Thanks Daphanie's sharing. Great' (2 msgs)"),
}


def normalize_phone(text):
    digits = re.sub(r"[^\d]", "", text)
    if digits.startswith("0"):
        digits = "60" + digits[1:]
    return digits


def get_key(row):
    name = row["name"]
    lines = name.strip().split("\n")
    if len(lines) >= 2:
        phone_line = lines[1].strip()
        if phone_line and not phone_line.startswith("("):
            return normalize_phone(phone_line)
    # Unknown lead — match by note content
    if "weekend work conflict" in row.get("notes", ""):
        return "__unknown__"
    return None


def main():
    rows = []
    with open(SRC, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    applied = 0
    unmatched = []

    for row in rows:
        if row["category"].strip() != "Still Considering":
            continue
        key = get_key(row)
        if key and key in OVERRIDES:
            cat, obj, ci, ca, notes = OVERRIDES[key]
            row["category"] = cat
            row["primary_objection"] = obj
            row["child_issue"] = ci
            row["child_age"] = ca
            row["notes"] = notes
            applied += 1
        else:
            unmatched.append((key, row["name"][:40]))

    print(f"Applied overrides: {applied}")
    if unmatched:
        print(f"Unmatched ({len(unmatched)}):")
        for k, n in unmatched:
            print(f"  key={k!r}  name={n!r}")

    for dst in DST_COPIES:
        with open(dst, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Written: {dst}")

    still = sum(1 for r in rows if r["category"] == "Still Considering")
    print(f"Remaining 'Still Considering': {still}")
    print(f"Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
