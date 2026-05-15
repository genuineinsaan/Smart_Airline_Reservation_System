import qrcode
from reportlab.lib.utils import ImageReader
from flask import make_response
from reportlab.pdfgen import canvas
from io import BytesIO
from flask import Flask, render_template, request, redirect, session
from config import SECRET_KEY
from utils.db_connection import get_db_connection

from datetime import datetime
import random
from ml_models.flight_prediction import (
    predict_delay,
    predict_price_category,
    predict_demand
)

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ---------------- HOME ROUTE ---------------- #

@app.route('/')
def home():

    return render_template('index.html')


# ---------------- USER LOGIN ---------------- #

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        entered_captcha = request.form['captcha']

        actual_captcha = request.form['actual_captcha']

        # CAPTCHA VALIDATION

        if entered_captcha.upper() != actual_captcha.upper():

            return "Invalid CAPTCHA"

        email = request.form['email']

        password = request.form['password']

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT * FROM users
        WHERE email=%s AND password=%s
        """

        values = (email, password)

        cursor.execute(query, values)

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            session['user_id'] = user['user_id']

            session['user_name'] = (
                user['first_name'] + " " + user['last_name']
            )

            # SMART REDIRECT

            if 'next_page' in session:

                next_page = session['next_page']

                session.pop('next_page', None)

                return redirect(next_page)

            # REDIRECT TO HOME PAGE

            return redirect('/')

        else:

            return "Invalid Email or Password"

    return render_template('login.html')


# ---------------- USER DASHBOARD ---------------- #

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:

        return redirect('/login')

    user_id = session['user_id']

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)


    # ---------------- USER DETAILS ---------------- #

    user_query = """
    SELECT

        CONCAT(first_name, ' ', last_name) AS full_name,
        email,
        phone,
        gender,
        country,
        unique_user_id

    FROM users

    WHERE user_id=%s
    """

    cursor.execute(user_query, (user_id,))

    user = cursor.fetchone()


    # ---------------- USER BOOKINGS ---------------- #

    booking_query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.booking_status,

        flights.airline_name,
        flights.source,
        flights.destination

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    WHERE reservations.user_id=%s

    ORDER BY reservations.reservation_id DESC
    """

    cursor.execute(booking_query, (user_id,))

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()


    return render_template(

        'dashboard.html',

        user=user,
        bookings=bookings

    )

# ---------------- EDIT PROFILE ---------------- #

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():

    # LOGIN CHECK

    if 'user_id' not in session:

        return redirect('/login')

    user_id = session['user_id']

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)


    # ---------------- UPDATE PROFILE ---------------- #

    if request.method == 'POST':

        first_name = request.form['first_name']

        last_name = request.form['last_name']

        email = request.form['email']

        phone = request.form['phone']

        country = request.form['country']

        password = request.form['password']


        # IF PASSWORD ENTERED

        if password != "":

            update_query = """
            UPDATE users

            SET

                first_name=%s,
                last_name=%s,
                email=%s,
                phone=%s,
                country=%s,
                password=%s

            WHERE user_id=%s
            """

            values = (

                first_name,
                last_name,
                email,
                phone,
                country,
                password,
                user_id

            )

        else:

            update_query = """
            UPDATE users

            SET

                first_name=%s,
                last_name=%s,
                email=%s,
                phone=%s,
                country=%s

            WHERE user_id=%s
            """

            values = (

                first_name,
                last_name,
                email,
                phone,
                country,
                user_id

            )

        cursor.execute(update_query, values)

        connection.commit()

        return redirect('/dashboard')


    # ---------------- FETCH USER DETAILS ---------------- #

    fetch_query = """
    SELECT *

    FROM users

    WHERE user_id=%s
    """

    cursor.execute(fetch_query, (user_id,))

    user = cursor.fetchone()

    cursor.close()
    connection.close()


    return render_template(

        'edit_profile.html',

        user=user

    )

# ---------------- USER REGISTER ---------------- #

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        first_name = request.form['first_name']

        middle_name = request.form['middle_name']

        last_name = request.form['last_name']

        email = request.form['email']

        phone = request.form['phone']

        password = request.form['password']

        gender = request.form['gender']

        dob = request.form['dob']

        country = request.form['country']

        address = request.form['address']

        profile_image = ""

        unique_user_id = "ARS" + str(random.randint(10000, 99999))

        connection = get_db_connection()

        cursor = connection.cursor()

        query = """
        INSERT INTO users(

            first_name,
            middle_name,
            last_name,
            email,
            phone,
            password,
            gender,
            dob,
            country,
            address,
            profile_image,
            unique_user_id

        )

        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (

            first_name,
            middle_name,
            last_name,
            email,
            phone,
            password,
            gender,
            dob,
            country,
            address,
            profile_image,
            unique_user_id

        )

        cursor.execute(query, values)

        connection.commit()

        cursor.close()
        connection.close()

        return redirect('/login')

    return render_template('register.html')


# ---------------- SEARCH FLIGHTS ---------------- #

@app.route('/search-flights', methods=['GET', 'POST'])
def search_flights():

    flights = []

    if request.method == 'POST':

        source = request.form['source']

        destination = request.form['destination']

        departure_date = request.form['departure_date']

        price_filter = request.form.get('price_filter')

        stops_filter = request.form.get('stops_filter')

        # CONVERT DATE TO DAY

        selected_day = datetime.strptime(
            departure_date,
            "%Y-%m-%d"
        ).strftime("%A")

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT * FROM flights

        WHERE source=%s
        AND destination=%s
        AND available_day=%s
        """

        filters = [
            source,
            destination,
            selected_day
        ]

        #PRICE FILTER 
        if price_filter == "low":
            query += " AND ticket_price < 5000"

        elif price_filter == "medium":
            query += " AND ticket_price BETWEEN 5000 AND 10000"

        elif price_filter == "high":
            query += " AND ticket_price > 10000"


         # STOPS FILTER
        if stops_filter != "":
            query += " AND stops=%s"
            filters.append(stops_filter)

        # SORT LOWEST PRICE FIRST
        query += " ORDER BY ticket_price ASC"

        cursor.execute(
            query,
            tuple(filters)
        )




        flights = cursor.fetchall()

        cursor.close()
        connection.close()

    return render_template(
        'search_flights.html',
        flights=flights
    )


# ---------------- FLIGHT DETAILS ---------------- #

@app.route('/flight-details/<int:flight_id>')
def flight_details(flight_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT * FROM flights
    WHERE flight_id=%s
    """

    cursor.execute(query, (flight_id,))

    flight = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        'flight_details.html',
        flight=flight
    )


# ---------------- BOOK FLIGHT ---------------- #

@app.route('/book-flight/<int:flight_id>', methods=['GET', 'POST'])
def book_flight(flight_id):

    # LOGIN CHECK

    if 'user_id' not in session:

        session['next_page'] = f'/book-flight/{flight_id}'

        return redirect('/login')

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    # ---------------- GET FLIGHT DETAILS ---------------- #

    query = """
    SELECT * FROM flights
    WHERE flight_id=%s
    """

    cursor.execute(query, (flight_id,))

    flight = cursor.fetchone()


    # ---------------- FETCH BOOKED SEATS ---------------- #

    booked_query = """
    SELECT seat_number

    FROM reservations

    WHERE flight_id=%s
    """

    cursor.execute(booked_query, (flight_id,))

    booked_seats_data = cursor.fetchall()

    booked_seats = [

        seat['seat_number']
        for seat in booked_seats_data

    ]


    # ---------------- DYNAMIC SEAT PRICING ---------------- #

    base_price = float(flight['ticket_price'])

    seat_prices = {

        "A": base_price + 2000,
        "B": base_price + 1500,
        "C": base_price + 1000,
        "D": base_price + 500,
        "E": base_price

    }


    # ---------------- FLIGHT FULL CHECK ---------------- #

    if flight['available_seats'] <= 0:

        cursor.close()
        connection.close()

        return "Flight Fully Booked"


    # ---------------- BOOKING PROCESS ---------------- #

    if request.method == 'POST':

        seat_number = request.form['seat_number']

        user_id = session['user_id']


        # ---------------- DUPLICATE SEAT CHECK ---------------- #

        if seat_number in booked_seats:

            cursor.close()
            connection.close()

            return "Seat Already Booked"


        # ---------------- SEAT ROW ---------------- #

        seat_row = seat_number[0]


        # ---------------- FINAL PRICE ---------------- #

        final_ticket_price = seat_prices[seat_row]


        session['booking_data'] = {
            'user_id': user_id,
            'flight_id': flight_id,
            'seat_number': seat_number,
            'final_ticket_price': final_ticket_price
}

        cursor.close()
        connection.close()

        return redirect('/payment')


        return redirect(f'/ticket/{reservation_id}')


    cursor.close()
    connection.close()

    return render_template(

        'book_flight.html',

        flight=flight,
        seat_prices=seat_prices,
        booked_seats=booked_seats

    )

# ---------------- CANCEL TICKET ---------------- #

@app.route('/cancel-ticket/<int:reservation_id>',
           methods=['GET', 'POST'])

def cancel_ticket(reservation_id):

    # LOGIN CHECK

    if 'user_id' not in session:

        return redirect('/login')

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)


    # ---------------- FETCH BOOKING ---------------- #

    query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.final_ticket_price,

        flights.flight_id,
        flights.airline_name,
        flights.source,
        flights.destination

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    WHERE reservations.reservation_id=%s
    """

    cursor.execute(query, (reservation_id,))

    booking = cursor.fetchone()


    # ---------------- INVALID BOOKING ---------------- #

    if not booking:

        cursor.close()
        connection.close()

        return "Invalid Booking"


    # ---------------- REFUND CALCULATION ---------------- #

    ticket_price = float(booking['final_ticket_price'])

    cancellation_fee = round(ticket_price * 0.20, 2)

    refund_amount = round(ticket_price - cancellation_fee, 2)


    # ---------------- CONFIRM CANCELLATION ---------------- #

    if request.method == 'POST':

        cancel_reason = request.form['cancel_reason']


        # ---------------- DELETE RESERVATION ---------------- #

        delete_query = """
        DELETE FROM reservations

        WHERE reservation_id=%s
        """

        cursor.execute(delete_query, (reservation_id,))


        # ---------------- RESTORE SEAT ---------------- #

        update_query = """
        UPDATE flights

        SET available_seats = available_seats + 1

        WHERE flight_id=%s
        """

        cursor.execute(
            update_query,
            (booking['flight_id'],)
        )

        connection.commit()

        cursor.close()
        connection.close()

        return render_template(
            'cancel_success.html',
            cancellation_fee=cancellation_fee,
            refund_amount=refund_amount
        )

    cursor.close()
    connection.close()

    return render_template(

        'cancel_ticket.html',

        booking=booking,
        cancellation_fee=cancellation_fee,
        refund_amount=refund_amount

    )


# ---------------- TICKET PAGE ---------------- #

@app.route('/ticket/<int:reservation_id>')
def ticket(reservation_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.booking_status,
        reservations.final_ticket_price,

        flights.airline_name,
        flights.source,
        flights.destination,
        flights.departure_time,
        flights.arrival_time,

        CONCAT(
            users.first_name,
            ' ',
            users.last_name
        ) AS full_name,

        users.unique_user_id

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    JOIN users
    ON reservations.user_id = users.user_id

    WHERE reservations.reservation_id=%s
    """

    cursor.execute(query, (reservation_id,))

    booking = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        'ticket.html',
        booking=booking
    )

# ---------------- DOWNLOAD PDF TICKET ---------------- #

@app.route('/download-ticket/<int:reservation_id>')
def download_ticket(reservation_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.booking_status,
        reservations.final_ticket_price,

        flights.airline_name,
        flights.source,
        flights.destination,
        flights.departure_time,
        flights.arrival_time,

        CONCAT(
            users.first_name,
            ' ',
            users.last_name
        ) AS full_name,

        users.unique_user_id

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    JOIN users
    ON reservations.user_id = users.user_id

    WHERE reservations.reservation_id=%s
    """

    cursor.execute(query, (reservation_id,))

    booking = cursor.fetchone()

    cursor.close()
    connection.close()


    # ---------------- PDF GENERATION ---------------- #

    pdf_buffer = BytesIO()

    pdf = canvas.Canvas(pdf_buffer)

    pdf.setTitle("Flight Ticket")


    # ---------------- HEADER ---------------- #

    pdf.setFillColorRGB(0.05, 0.24, 0.60)

    pdf.rect(
        0,
        760,
        600,
        80,
        fill=1
    )

    pdf.setFillColorRGB(1, 1, 1)

    pdf.setFont(
        "Helvetica-Bold",
        28
    )

    pdf.drawString(
        180,
        790,
        "FLIGHT TICKET"
    )


    # ---------------- AIRLINE NAME ---------------- #

    pdf.setFillColorRGB(0.05, 0.24, 0.60)

    pdf.setFont(
        "Helvetica-Bold",
        24
    )

    pdf.drawString(
        60,
        720,
        booking['airline_name']
    )

    pdf.setFont(
        "Helvetica",
        14
    )

    pdf.drawString(
        60,
        695,
        f"{booking['source']} → {booking['destination']}"
    )


    # ---------------- PRICE BOX ---------------- #

    pdf.setFillColorRGB(0.05, 0.24, 0.60)

    pdf.roundRect(
        390,
        675,
        140,
        55,
        10,
        fill=1
    )

    pdf.setFillColorRGB(1, 1, 1)

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawString(
        420,
        700,
        f"Rs{booking['final_ticket_price']}"
    )


    # ---------------- USER ID BOX ---------------- #

    pdf.setFillColorRGB(0.10, 0.35, 0.85)

    pdf.roundRect(
        60,
        620,
        470,
        50,
        10,
        fill=1
    )

    pdf.setFillColorRGB(1, 1, 1)

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        80,
        648,
        "AIRLINE CUSTOMER ID"
    )

    pdf.setFont(
        "Helvetica-Bold",
        22
    )

    pdf.drawString(
        80,
        628,
        booking['unique_user_id']
    )


    # ---------------- DETAILS ---------------- #

    details = [

        ("Passenger Name", booking['full_name']),
        ("Seat Number", booking['seat_number']),
        ("Departure Time", str(booking['departure_time'])),
        ("Arrival Time", str(booking['arrival_time'])),
        ("Booking Status", booking['booking_status']),
        ("Ticket ID", f"#{booking['reservation_id']}")

    ]

    x_positions = [60, 300]

    y = 540

    box_width = 220

    box_height = 70

    index = 0


    for label, value in details:

        x = x_positions[index % 2]

        if index % 2 == 0 and index != 0:

            y -= 90


        pdf.setFillColorRGB(0.96, 0.97, 0.99)

        pdf.roundRect(
            x,
            y,
            box_width,
            box_height,
            10,
            fill=1
        )

        pdf.setFillColorRGB(0.05, 0.24, 0.60)

        pdf.setFont(
            "Helvetica-Bold",
            11
        )

        pdf.drawString(
            x + 15,
            y + 45,
            label
        )

        pdf.setFillColorRGB(0, 0, 0)

        pdf.setFont(
            "Helvetica",
            14
        )

        pdf.drawString(
            x + 15,
            y + 22,
            str(value)
        )

        index += 1

    # ---------------- QR CODE ---------------- #

    qr_data = f"""

    Ticket ID:
    {booking['reservation_id']}

    Passenger:
    {booking['full_name']}

    Airline:
     {booking['airline_name']}

     Route:
    {booking['source']} to {booking['destination']}

    Seat:
    {booking['seat_number']}

    """

    qr = qrcode.make(qr_data)

    qr_buffer = BytesIO()

    qr.save(qr_buffer)

    qr_buffer.seek(0)

    qr_image = ImageReader(qr_buffer)

    pdf.drawImage(

        qr_image,

        400,
        210,

        width=110,
        height=110

    )


    # QR LABEL

    pdf.setFillColorRGB(0.3, 0.3, 0.3)

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        410,
        195,
        "Scan Boarding QR"
    )

    # ---------------- FOOTER ---------------- #

    pdf.setStrokeColorRGB(0.85, 0.85, 0.85)

    pdf.line(
        60,
        180,
        530,
        180
    )

    pdf.setFillColorRGB(0.35, 0.35, 0.35)

    pdf.setFont(
        "Helvetica-Oblique",
        12
    )

    pdf.drawString(
        140,
        150,
        "Thank you for choosing Airline Reservation System"
    )


    # ---------------- SAVE PDF ---------------- #

    pdf.save()

    pdf_buffer.seek(0)


    # ---------------- RESPONSE ---------------- #

    response = make_response(
        pdf_buffer.getvalue()
    )

    response.headers['Content-Type'] = 'application/pdf'

    response.headers['Content-Disposition'] = (

        f'attachment; '
        f'filename=ticket_{reservation_id}.pdf'

    )

    return response

# ---------------- MY BOOKINGS ---------------- #

@app.route('/my-bookings')
def my_bookings():

    # LOGIN CHECK

    if 'user_id' not in session:

        return redirect('/login')

    user_id = session['user_id']

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.booking_status,

        flights.airline_name,
        flights.source,
        flights.destination

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    WHERE reservations.user_id=%s

    ORDER BY reservations.reservation_id DESC
    """

    cursor.execute(query, (user_id,))

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'my_bookings.html',
        bookings=bookings
    )

# ---------------- VIEW RESERVATIONS ---------------- #

@app.route('/view-reservations')

def view_reservations():

    # ADMIN LOGIN CHECK

    if 'admin_id' not in session:

        return redirect('/admin-login')

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT

        reservations.reservation_id,
        reservations.seat_number,
        reservations.booking_status,
        reservations.final_ticket_price,

        flights.airline_name,
        flights.source,
        flights.destination,

        CONCAT(
            users.first_name,
            ' ',
            users.last_name
        ) AS passenger_name,

        payments.payment_method

    FROM reservations

    JOIN flights
    ON reservations.flight_id = flights.flight_id

    JOIN users
    ON reservations.user_id = users.user_id

    LEFT JOIN payments
    ON reservations.reservation_id =
    payments.reservation_id

    ORDER BY reservations.reservation_id DESC
    """

    cursor.execute(query)

    reservations = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(

        'view_reservations.html',

        reservations=reservations

    )


# ---------------- MANAGE USERS ---------------- #

@app.route('/manage-users')

def manage_users():

    if 'admin_id' not in session:

        return redirect('/admin-login')

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT

        user_id,
        unique_user_id,

        CONCAT(
            first_name,
            ' ',
            last_name
        ) AS full_name,

        email,
        phone,
        gender,
        country

    FROM users

    ORDER BY user_id DESC
    """

    cursor.execute(query)

    users = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(

        'manage_users.html',

        users=users

    )

# ---------------- SMART FLIGHT INSIGHTS ---------------- #

@app.route('/smart-flight-insights',
           methods=['GET', 'POST'])

def smart_flight_insights():

    if 'admin_id' not in session:

        return redirect('/admin-login')

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    flights = []

    summary = None


    # FETCH UNIQUE ROUTES

    route_query = """
    SELECT DISTINCT source, destination
    FROM flights
    """

    cursor.execute(route_query)

    routes = cursor.fetchall()


    # FORM SUBMIT

    if request.method == 'POST':

        source = request.form['source']

        destination = request.form['destination']


        # FETCH FLIGHTS

        flight_query = """
        SELECT *

        FROM flights

        WHERE source=%s
        AND destination=%s
        """

        cursor.execute(
            flight_query,
            (source, destination)
        )

        flights = cursor.fetchall()


        # ROUTE SUMMARY

        total_flights = len(flights)

        avg_price = 0

        if total_flights > 0:

            avg_price = round(

                sum(
                    float(f['ticket_price'])
                    for f in flights
                ) / total_flights

            )


        summary = {

            'source': source,
            'destination': destination,
            'total_flights': total_flights,
            'avg_price': avg_price

        }


    cursor.close()
    connection.close()

    return render_template(

        'smart_flight_insights.html',

        routes=routes,
        flights=flights,
        summary=summary

    )


# ---------------- ADMIN LOGIN ---------------- #

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']

        password = request.form['password']

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT * FROM admins
        WHERE username=%s AND password=%s
        """

        values = (username, password)

        cursor.execute(query, values)

        admin = cursor.fetchone()

        cursor.close()
        connection.close()

        if admin:

            session['admin_id'] = admin['admin_id']

            session['admin_username'] = admin['username']

            return redirect('/admin-dashboard')

        else:

            return "Invalid Admin Credentials"

    return render_template('admin_login.html')


# ---------------- ADMIN DASHBOARD ---------------- #

@app.route('/admin-dashboard')
def admin_dashboard():

    if 'admin_id' in session:

        return render_template('admin_dashboard.html')

    return redirect('/admin-login')


# ---------------- MANAGE FLIGHTS ---------------- #

@app.route('/manage-flights', methods=['GET', 'POST'])
def manage_flights():

    if 'admin_id' not in session:

        return redirect('/admin-login')

    if request.method == 'POST':

        airline_name = request.form['airline_name']

        source = request.form['source']

        destination = request.form['destination']

        available_day = request.form['available_day']

        departure_time = request.form['departure_time']

        arrival_time = request.form['arrival_time']

        duration = request.form['duration']

        stops = request.form['stops']

        available_seats = 15

        ticket_price = request.form['ticket_price']

        weather_status = request.form['weather_status']

        # ---------------- VIEW RESERVATIONS ---------------- #

        @app.route('/view-reservations')
        def view_reservations():
            if 'admin_id' not in session:
                return redirect('/admin-login')
            connection = get_db_connection()

            cursor = connection.cursor(dictionary=True)

            query = """
            SELECT
                reservations.reservation_id,
            reservations.seat_number,
            reservations.booking_status,
            reservations.final_ticket_price,

            flights.airline_name,
            flights.source,
            flights.destination,

            CONCAT(
                users.first_name,
                ' ',
                users.last_name
            ) AS passenger_name,

            payments.payment_method,
            payments.transaction_id

        FROM reservations

        JOIN flights
        ON reservations.flight_id = flights.flight_id

        JOIN users
        ON reservations.user_id = users.user_id

        LEFT JOIN payments
        ON reservations.reservation_id =
        payments.reservation_id

        ORDER BY reservations.reservation_id DESC
        """
            
            cursor.execute(query)

            reservations = cursor.fetchall()

            cursor.close()
            connection.close()

            return render_template(

                'view_reservations.html',

                reservations=reservations
            )    

        # ---------------- AI PREDICTIONS ---------------- #

        delay_prediction = predict_delay(
            weather_status,
            stops
        )

        price_category = predict_price_category(
            ticket_price
        )

        demand_prediction = predict_demand()    

        connection = get_db_connection()

        cursor = connection.cursor()

        query = """
        INSERT INTO flights(

            airline_name,
            source,
            destination,
            available_day,
            departure_time,
            arrival_time,
            duration,
            stops,
            available_seats,
            ticket_price,
            weather_status,
            delay_prediction

        )

        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (

            airline_name,
            source,
            destination,
            available_day,
            departure_time,
            arrival_time,
            duration,
            stops,
            available_seats,
            ticket_price,
            weather_status,
            delay_prediction

        )

        cursor.execute(query, values)

        connection.commit()

        cursor.close()
        connection.close()

        return "Flight Added Successfully!"

    return render_template('manage_flights.html')

# ---------------- PAYMENT PAGE ---------------- #

@app.route('/payment', methods=['GET', 'POST'])

def payment():

    if 'booking_data' not in session:

        return redirect('/')

    booking_data = session['booking_data']

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT * FROM flights
    WHERE flight_id=%s
    """

    cursor.execute(
        query,
        (booking_data['flight_id'],)
    )

    flight = cursor.fetchone()


    # PAYMENT SUCCESS

    if request.method == 'POST':

        payment_method = request.form['payment_method']

        card_holder_name = request.form['card_holder_name']

        card_number = request.form['card_number']

        expiry = request.form['expiry']

        cvv = request.form['cvv']


        # LAST 4 DIGITS

        last_digits = card_number[-4:]


        # TRANSACTION ID

        transaction_id = (
            "TXN" +
            str(random.randint(100000, 999999))
        )


        # INSERT RESERVATION

        insert_query = """
        INSERT INTO reservations(

            user_id,
            flight_id,
            seat_number,
            booking_status,
            final_ticket_price

        )

        VALUES(%s,%s,%s,%s,%s)
        """

        values = (

            booking_data['user_id'],
            booking_data['flight_id'],
            booking_data['seat_number'],
            'Confirmed',
            booking_data['final_ticket_price']

        )

        cursor.execute(insert_query, values)

        reservation_id = cursor.lastrowid


        # STORE PAYMENT

        payment_query = """
        INSERT INTO payments(

            reservation_id,
            card_holder_name,
            payment_method,
            card_last_digits,
            transaction_id,
            payment_status

        )

        VALUES(%s,%s,%s,%s,%s,%s)
        """

        payment_values = (

            reservation_id,
            card_holder_name,
            payment_method,
            last_digits,
            transaction_id,
            'Success'

        )

        cursor.execute(
            payment_query,
            payment_values
        )


        # REDUCE SEATS

        update_query = """
        UPDATE flights

        SET available_seats = available_seats - 1

        WHERE flight_id=%s
        """

        cursor.execute(
            update_query,
            (booking_data['flight_id'],)
        )

        connection.commit()

        session.pop('booking_data', None)

        cursor.close()
        connection.close()

        return redirect(
            f'/ticket/{reservation_id}'
        )


    cursor.close()
    connection.close()

    return render_template(

        'payment.html',

        flight=flight,

        final_ticket_price=
        booking_data['final_ticket_price']

    )

# ---------------- LOGOUT ---------------- #

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


# ---------------- RUN FLASK APP ---------------- #

if __name__ == '__main__':

    app.run(debug=True)