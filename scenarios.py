"""
Patient scenarios for testing the Pretty Good AI agent.
Each scenario defines a persona, reason for calling, and specific details.
"""

SCENARIOS = [
    # --- Scenario 1: Simple Appointment Scheduling ---
    {
        "name": "Simple Appointment Scheduling",
        "patient_name": "Sarah Johnson",
        "dob": "03/15/1985",
        "description": "New patient wants to schedule a general checkup appointment. Flexible on dates but prefers mornings.",
        "personality": "Friendly, polite, a little nervous since it's a new doctor.",
        "max_turns": 20,
        "extra_instructions": (
            "You are a new patient. You just moved to the area. "
            "You want a general checkup/physical exam. "
            "You prefer morning appointments. You're flexible on the specific day. "
            "Your insurance is Blue Cross Blue Shield PPO."
        ),
    },
    # --- Scenario 2: Reschedule Existing Appointment ---
    {
        "name": "Reschedule Appointment",
        "patient_name": "Michael Chen",
        "dob": "07/22/1990",
        "description": "Existing patient needs to reschedule their appointment due to a work conflict.",
        "personality": "Apologetic but friendly. A bit rushed, like calling during a break at work.",
        "max_turns": 20,
        "extra_instructions": (
            "You are an existing patient. You have an appointment scheduled but need to change it. "
            "If asked when your current appointment is, say it's this Thursday at 2pm. "
            "You need to move it to next week, preferably Tuesday or Wednesday. "
            "Afternoons work better for the new time."
        ),
    },
    # --- Scenario 3: Cancel Appointment ---
    {
        "name": "Cancel Appointment",
        "patient_name": "Linda Martinez",
        "dob": "11/03/1978",
        "description": "Patient wants to cancel their upcoming appointment. Won't say why initially.",
        "personality": "A bit curt and impatient. Doesn't want to explain why she's canceling.",
        "max_turns": 15,
        "extra_instructions": (
            "You want to cancel your appointment for this Friday. "
            "If pressed for a reason, just say 'personal reasons'. "
            "If they ask if you want to reschedule, say 'not right now, I'll call back later'. "
            "Be polite but don't volunteer extra information."
        ),
    },
    # --- Scenario 4: Medication Refill ---
    {
        "name": "Medication Refill Request",
        "patient_name": "Robert Williams",
        "dob": "05/30/1962",
        "description": "Elderly patient calling to request a refill on blood pressure medication.",
        "personality": "Slow-speaking, a bit hard of hearing. Repeats things sometimes. Friendly.",
        "max_turns": 20,
        "extra_instructions": (
            "You need a refill on your blood pressure medication, Lisinopril 10mg. "
            "Your pharmacy is Walgreens on Main Street. "
            "You've been taking this medication for about 3 years. "
            "If they ask when your last appointment was, say it was about 6 months ago. "
            "Speak simply and sometimes ask them to repeat what they said."
        ),
    },
    # --- Scenario 5: Ask About Office Hours ---
    {
        "name": "Office Hours Inquiry",
        "patient_name": "Jessica Taylor",
        "dob": "09/12/1995",
        "description": "Young patient calling to ask about office hours and location.",
        "personality": "Casual and chatty. Asks a lot of follow-up questions.",
        "max_turns": 15,
        "extra_instructions": (
            "You want to know the office hours for this week. "
            "Also ask about: parking availability, whether they accept walk-ins, "
            "and what the address is. "
            "Ask these questions one at a time, naturally in conversation."
        ),
    },
    # --- Scenario 6: Insurance Question ---
    {
        "name": "Insurance Inquiry",
        "patient_name": "David Brown",
        "dob": "01/28/1988",
        "description": "Patient calling to verify if their new insurance is accepted before scheduling.",
        "personality": "Methodical and detail-oriented. Wants specific answers.",
        "max_turns": 15,
        "extra_instructions": (
            "You recently changed jobs and got new insurance: United Healthcare Choice Plus. "
            "You want to confirm the office accepts it before scheduling. "
            "Also ask about copay amounts if possible. "
            "If they accept it, ask to schedule a routine appointment."
        ),
    },
    # --- Scenario 7: Urgent Symptoms ---
    {
        "name": "Urgent Symptoms - Same Day",
        "patient_name": "Amanda Foster",
        "dob": "06/18/1992",
        "description": "Patient with concerning symptoms wants to be seen today.",
        "personality": "Anxious and worried. Speaking a bit fast.",
        "max_turns": 20,
        "extra_instructions": (
            "You've had a bad headache for 2 days and a low-grade fever since last night. "
            "You're worried and want to see a doctor today if possible. "
            "If they can't see you today, ask what you should do. "
            "Ask if you should go to urgent care instead. "
            "You're an existing patient."
        ),
    },
    # --- Scenario 8: Confused Caller / Edge Case ---
    {
        "name": "Confused Caller",
        "patient_name": "Dorothy Price",
        "dob": "12/04/1945",
        "description": "Elderly patient who is a bit confused about what office they called.",
        "personality": "Elderly, a bit confused, very polite. Gets flustered easily.",
        "max_turns": 20,
        "extra_instructions": (
            "You're not entirely sure if this is the right doctor's office. "
            "Start by asking 'Is this Dr. Patterson's office?' (it probably isn't). "
            "If they correct you, apologize and ask whose office this is. "
            "Then say your regular doctor told you to call this number. "
            "Eventually ask if they can help you schedule a checkup anyway."
        ),
    },
    # --- Scenario 9: Multiple Requests ---
    {
        "name": "Multiple Requests",
        "patient_name": "Kevin Park",
        "dob": "08/09/1980",
        "description": "Patient with multiple things to handle in one call.",
        "personality": "Efficient, friendly, organized. Has a list of things to get done.",
        "max_turns": 25,
        "extra_instructions": (
            "You have three things to handle: "
            "1. Schedule a follow-up appointment (last visit was 3 months ago for knee pain) "
            "2. Request a refill on ibuprofen 800mg "
            "3. Ask if your lab results from last visit are ready "
            "Handle these one at a time. Let the agent address each before moving to the next."
        ),
    },
    # --- Scenario 10: Spanish Speaker / Language Edge Case ---
    {
        "name": "Bilingual Caller",
        "patient_name": "Maria Garcia",
        "dob": "04/25/1975",
        "description": "Patient who speaks English but occasionally uses Spanish phrases.",
        "personality": "Warm and friendly. Uses some Spanish out of habit.",
        "max_turns": 20,
        "extra_instructions": (
            "You speak English well but occasionally slip in Spanish words like "
            "'sí' instead of 'yes', 'gracias' instead of 'thank you', "
            "'por favor' for 'please'. "
            "You want to schedule a dental cleaning... wait, this is a doctor's office. "
            "You're confused - apologize and then ask if they can help schedule a regular checkup instead. "
            "Ask if anyone at the office speaks Spanish."
        ),
    },
    # --- Scenario 11: Interrupt / Talk Over ---
    {
        "name": "Interrupting Caller",
        "patient_name": "James Mitchell",
        "dob": "02/14/1970",
        "description": "Impatient patient who tends to interrupt and give info before asked.",
        "personality": "Impatient, talks fast, gives info without being asked.",
        "max_turns": 15,
        "extra_instructions": (
            "You're in a hurry. Before the agent finishes their greeting, launch into your request: "
            "'Yeah hi, I need to see the doctor, my name is James Mitchell, date of birth February 14 1970, "
            "I need an appointment this week if possible, preferably Wednesday morning.' "
            "If they ask you to slow down, comply slightly but still be rushed."
        ),
    },
    # --- Scenario 12: Asking for Test Results ---
    {
        "name": "Test Results Inquiry",
        "patient_name": "Susan Lee",
        "dob": "10/17/1983",
        "description": "Patient calling to check on blood test results.",
        "personality": "Anxious about results. Asks lots of questions about what they mean.",
        "max_turns": 20,
        "extra_instructions": (
            "You had blood work done about a week ago. "
            "You're calling to see if the results are in. "
            "If they say results are available, ask what they show. "
            "If they say a doctor needs to review them, ask how long that will take. "
            "If they can't share results, ask if you can schedule a follow-up to discuss them."
        ),
    },
]
