import random


# ---------------- DELAY PREDICTION ---------------- #

def predict_delay(weather_status, stops):

    weather_status = weather_status.lower()


    # BAD WEATHER

    if weather_status in ["storm", "heavy rain", "fog"]:

        return "High Chance of Delay"


    # MEDIUM WEATHER

    elif weather_status in ["cloudy", "drizzle"]:

        return "Possible Delay"


    # MORE STOPS

    elif int(stops) >= 2:

        return "Moderate Delay Risk"


    # NORMAL

    else:

        return "On Time"



# ---------------- SMART PRICE CATEGORY ---------------- #

def predict_price_category(ticket_price):

    ticket_price = float(ticket_price)

    if ticket_price < 4000:

        return "Budget Flight"

    elif ticket_price < 8000:

        return "Standard Pricing"

    else:

        return "Premium Pricing"



# ---------------- DEMAND PREDICTION ---------------- #

def predict_demand():

    demand_list = [

        "High Demand",
        "Moderate Demand",
        "Low Demand"

    ]

    return random.choice(demand_list)