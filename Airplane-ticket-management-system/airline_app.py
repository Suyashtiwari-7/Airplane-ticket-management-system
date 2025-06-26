import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

# --- Database Management Class ---
class DatabaseManager:
    def __init__(self, db_name="airline.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.init_db()

    def connect(self):
        """Establishes a connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to connect to database: {e}")
            self.conn = None

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

    def init_db(self):
        """
        Initializes the database by creating necessary tables if they don't exist.
        Tables:
        - flights: Stores flight details (ID, departure, destination, date, time, price, seats_available)
        - bookings: Stores booking details (ID, flight_id, passenger_name, num_seats, total_price)
        """
        if not self.conn:
            return

        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS flights (
                    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departure TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    flight_date TEXT NOT NULL,
                    flight_time TEXT NOT NULL,
                    price REAL NOT NULL,
                    seats_available INTEGER NOT NULL
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id INTEGER NOT NULL,
                    passenger_name TEXT NOT NULL,
                    num_seats INTEGER NOT NULL,
                    total_price REAL NOT NULL,
                    booking_date TEXT DEFAULT CURRENT_DATE,
                    FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
                )
            ''')
            self.conn.commit()
            self._add_dummy_data_if_empty() # Add some initial data for testing
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to initialize database tables: {e}")

    def _add_dummy_data_if_empty(self):
        """Adds some dummy flight data if the flights table is empty."""
        self.cursor.execute("SELECT COUNT(*) FROM flights")
        if self.cursor.fetchone()[0] == 0:
            dummy_flights = [
                ("New York", "London", "2025-07-01", "08:00", 750.00, 150),
                ("London", "Paris", "2025-07-02", "10:30", 200.00, 80),
                ("Paris", "Rome", "2025-07-03", "14:00", 150.00, 100),
                ("New York", "Tokyo", "2025-07-10", "18:00", 1200.00, 200),
                ("Tokyo", "Sydney", "2025-07-12", "22:00", 900.00, 120)
            ]
            self.cursor.executemany(
                "INSERT INTO flights (departure, destination, flight_date, flight_time, price, seats_available) VALUES (?, ?, ?, ?, ?, ?)",
                dummy_flights
            )
            self.conn.commit()
            print("Dummy flight data added.")

    def add_flight(self, departure, destination, date, time, price, seats):
        """Adds a new flight to the database."""
        if not self.conn: return False
        try:
            self.cursor.execute(
                "INSERT INTO flights (departure, destination, flight_date, flight_time, price, seats_available) VALUES (?, ?, ?, ?, ?, ?)",
                (departure, destination, date, time, price, seats)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add flight: {e}")
            return False

    def search_flights(self, departure, destination, date):
        """Searches for flights based on departure, destination, and date."""
        if not self.conn: return []
        try:
            query = "SELECT flight_id, departure, destination, flight_date, flight_time, price, seats_available FROM flights WHERE 1=1"
            params = []
            if departure:
                query += " AND departure LIKE ?"
                params.append(f"%{departure}%")
            if destination:
                query += " AND destination LIKE ?"
                params.append(f"%{destination}%")
            if date:
                query += " AND flight_date = ?"
                params.append(date)

            self.cursor.execute(query, tuple(params))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to search flights: {e}")
            return []

    def book_flight(self, flight_id, passenger_name, num_seats):
        """
        Books a flight for a passenger.
        Decreases available seats and records the booking.
        """
        if not self.conn: return False, "Database not connected."
        try:
            self.cursor.execute("SELECT price, seats_available FROM flights WHERE flight_id = ?", (flight_id,))
            flight_info = self.cursor.fetchone()

            if not flight_info:
                return False, "Flight not found."

            price, seats_available = flight_info
            if num_seats > seats_available:
                return False, f"Not enough seats available. Only {seats_available} seats left."

            total_price = price * num_seats
            
            # Decrease seats available
            self.cursor.execute(
                "UPDATE flights SET seats_available = ? WHERE flight_id = ?",
                (seats_available - num_seats, flight_id)
            )

            # Record booking
            self.cursor.execute(
                "INSERT INTO bookings (flight_id, passenger_name, num_seats, total_price) VALUES (?, ?, ?, ?)",
                (flight_id, passenger_name, num_seats, total_price)
            )
            self.conn.commit()
            return True, "Flight booked successfully!"
        except sqlite3.Error as e:
            self.conn.rollback() # Rollback in case of error
            return False, f"Error booking flight: {e}"

    def get_booking(self, booking_id):
        """Retrieves details of a specific booking."""
        if not self.conn: return None
        try:
            self.cursor.execute('''
                SELECT
                    b.booking_id,
                    f.departure,
                    f.destination,
                    f.flight_date,
                    f.flight_time,
                    b.passenger_name,
                    b.num_seats,
                    b.total_price,
                    f.price as price_per_seat
                FROM bookings b
                JOIN flights f ON b.flight_id = f.flight_id
                WHERE b.booking_id = ?
            ''', (booking_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to retrieve booking: {e}")
            return None

    def cancel_booking(self, booking_id):
        """
        Cancels a booking.
        Increases available seats for the corresponding flight and deletes the booking record.
        """
        if not self.conn: return False, "Database not connected."
        try:
            # Get booking details to update flight seats
            self.cursor.execute("SELECT flight_id, num_seats FROM bookings WHERE booking_id = ?", (booking_id,))
            booking_info = self.cursor.fetchone()

            if not booking_info:
                return False, "Booking not found."

            flight_id, num_seats = booking_info

            # Increase seats available for the flight
            self.cursor.execute(
                "UPDATE flights SET seats_available = seats_available + ? WHERE flight_id = ?",
                (num_seats, flight_id)
            )

            # Delete the booking record
            self.cursor.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))
            self.conn.commit()
            return True, "Booking cancelled successfully!"
        except sqlite3.Error as e:
            self.conn.rollback() # Rollback in case of error
            return False, f"Error cancelling booking: {e}"

# --- GUI Application Class ---
class AirlineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Airline Ticket Reservation System")
        self.geometry("800x600")
        self.db_manager = DatabaseManager()

        # Configure columns for responsiveness (optional, but good practice)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.create_widgets()
        
        # Bind the window closing event to close the database connection
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        """Handles closing the application and database connection."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.db_manager.close()
            self.destroy()

    def create_widgets(self):
        """Sets up all the GUI components."""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Search Flights Tab ---
        self.search_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.search_frame, text="Search Flights")
        self._create_search_tab()

        # --- Book Flight Tab ---
        self.book_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.book_frame, text="Book Flight")
        self._create_book_tab()

        # --- My Bookings Tab ---
        self.my_bookings_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.my_bookings_frame, text="My Bookings")
        self._create_my_bookings_tab()

        # --- Admin Tab (for adding flights) ---
        self.admin_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.admin_frame, text="Admin (Add Flight)")
        self._create_admin_tab()

    def _create_search_tab(self):
        """Creates widgets for the Search Flights tab."""
        # Input fields for search criteria
        input_frame = ttk.LabelFrame(self.search_frame, text="Search Criteria", padding="10")
        input_frame.pack(pady=10, fill="x")

        ttk.Label(input_frame, text="Departure:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.search_departure_entry = ttk.Entry(input_frame, width=30)
        self.search_departure_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(input_frame, text="Destination:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.search_destination_entry = ttk.Entry(input_frame, width=30)
        self.search_destination_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(input_frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.search_date_entry = ttk.Entry(input_frame, width=30)
        self.search_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        search_button = ttk.Button(input_frame, text="Search Flights", command=self._search_flights_gui)
        search_button.grid(row=0, column=2, rowspan=3, padx=10, pady=5, sticky="ns")

        input_frame.grid_columnconfigure(1, weight=1) # Allow entry field to expand

        # Results display (Treeview)
        results_frame = ttk.LabelFrame(self.search_frame, text="Available Flights", padding="10")
        results_frame.pack(pady=10, fill="both", expand=True)

        columns = ("ID", "Departure", "Destination", "Date", "Time", "Price", "Seats")
        self.flights_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        # Define column headings
        for col in columns:
            self.flights_tree.heading(col, text=col, anchor="w")
            self.flights_tree.column(col, width=100, anchor="w") # Default width
        
        self.flights_tree.column("ID", width=50)
        self.flights_tree.column("Price", width=70, anchor="e")
        self.flights_tree.column("Seats", width=60, anchor="e")

        self.flights_tree.pack(side="left", fill="both", expand=True)

        # Scrollbar for the Treeview
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.flights_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.flights_tree.configure(yscrollcommand=scrollbar.set)

    def _create_book_tab(self):
        """Creates widgets for the Book Flight tab."""
        book_frame_content = ttk.Frame(self.book_frame, padding="10")
        book_frame_content.pack(expand=True)

        ttk.Label(book_frame_content, text="Flight ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.book_flight_id_entry = ttk.Entry(book_frame_content, width=30)
        self.book_flight_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(book_frame_content, text="Passenger Name:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.book_passenger_name_entry = ttk.Entry(book_frame_content, width=30)
        self.book_passenger_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(book_frame_content, text="Number of Seats:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.book_num_seats_entry = ttk.Entry(book_frame_content, width=30)
        self.book_num_seats_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        book_button = ttk.Button(book_frame_content, text="Book Flight", command=self._book_flight_gui)
        book_button.grid(row=3, column=0, columnspan=2, pady=10)

        book_frame_content.grid_columnconfigure(1, weight=1)

    def _create_my_bookings_tab(self):
        """Creates widgets for the My Bookings tab."""
        my_bookings_frame_content = ttk.Frame(self.my_bookings_frame, padding="10")
        my_bookings_frame_content.pack(expand=True, fill="both")

        input_frame = ttk.Frame(my_bookings_frame_content)
        input_frame.pack(pady=10)

        ttk.Label(input_frame, text="Booking ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.booking_id_entry = ttk.Entry(input_frame, width=30)
        self.booking_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        retrieve_button = ttk.Button(input_frame, text="Retrieve Booking", command=self._view_booking_gui)
        retrieve_button.grid(row=0, column=2, padx=10, pady=5)

        self.booking_details_label = ttk.Label(my_bookings_frame_content, text="Booking Details:\n", justify="left")
        self.booking_details_label.pack(pady=10, fill="x")

        cancel_button = ttk.Button(my_bookings_frame_content, text="Cancel Booking", command=self._cancel_booking_gui)
        cancel_button.pack(pady=10)
        
        my_bookings_frame_content.grid_columnconfigure(0, weight=1)

    def _create_admin_tab(self):
        """Creates widgets for the Admin (Add Flight) tab."""
        admin_frame_content = ttk.Frame(self.admin_frame, padding="10")
        admin_frame_content.pack(expand=True, fill="both")
        labels = ["Departure:", "Destination:", "Date (YYYY-MM-DD):", "Time (HH:MM):", "Price:", "Seats Available:"]
        self.admin_entries = {}
        for i, text in enumerate(labels):
            ttk.Label(admin_frame_content, text=text).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            entry = ttk.Entry(admin_frame_content, width=40)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            # Use rsplit to handle colons in label text
            key = text.rsplit(':', 1)[0].strip().lower().replace(' ', '_')
            self.admin_entries[key] = entry
        print('Admin entries keys:', list(self.admin_entries.keys()))  # Debug print
        # Rename for easier access, using the correct keys based on generation logic
        self.admin_departure_entry = self.admin_entries['departure']
        self.admin_destination_entry = self.admin_entries['destination']
        self.admin_date_entry = self.admin_entries['date_(yyyy-mm-dd)']
        self.admin_time_entry = self.admin_entries['time_(hh:mm)']
        self.admin_price_entry = self.admin_entries['price']
        self.admin_seats_available_entry = self.admin_entries['seats_available']

        add_flight_button = ttk.Button(admin_frame_content, text="Add Flight", command=self._add_flight_gui)
        add_flight_button.grid(row=len(labels), column=0, columnspan=2, pady=15)

        admin_frame_content.grid_columnconfigure(1, weight=1)

    # --- GUI Event Handlers ---
    def _search_flights_gui(self):
        """Handles the search flights button click."""
        departure = self.search_departure_entry.get().strip()
        destination = self.search_destination_entry.get().strip()
        date = self.search_date_entry.get().strip()

        # Basic date format validation
        if date and not self._is_valid_date(date):
            messagebox.showerror("Invalid Input", "Please enter date in YYYY-MM-DD format.")
            return

        flights = self.db_manager.search_flights(departure, destination, date)
        
        # Clear existing entries in the treeview
        for item in self.flights_tree.get_children():
            self.flights_tree.delete(item)

        if not flights:
            messagebox.showinfo("Search Results", "No flights found matching your criteria.")
            return

        # Insert new data
        for flight in flights:
            self.flights_tree.insert("", "end", values=flight)

    def _book_flight_gui(self):
        """Handles the book flight button click."""
        flight_id_str = self.book_flight_id_entry.get().strip()
        passenger_name = self.book_passenger_name_entry.get().strip()
        num_seats_str = self.book_num_seats_entry.get().strip()

        if not flight_id_str or not passenger_name or not num_seats_str:
            messagebox.showerror("Input Error", "All fields are required for booking.")
            return

        try:
            flight_id = int(flight_id_str)
            num_seats = int(num_seats_str)
            if num_seats <= 0:
                raise ValueError("Number of seats must be positive.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Flight ID and Number of Seats must be valid integers.")
            return

        success, message = self.db_manager.book_flight(flight_id, passenger_name, num_seats)
        if success:
            # Get the last booking ID
            booking_id = None
            try:
                self.db_manager.cursor.execute("SELECT last_insert_rowid()")
                booking_id = self.db_manager.cursor.fetchone()[0]
            except Exception:
                booking_id = None
            if booking_id:
                messagebox.showinfo("Booking Success", f"{message}\nYour Booking ID is: {booking_id}")
            else:
                messagebox.showinfo("Booking Success", message)
            # Clear input fields after successful booking
            self.book_flight_id_entry.delete(0, tk.END)
            self.book_passenger_name_entry.delete(0, tk.END)
            self.book_num_seats_entry.delete(0, tk.END)
            # Refresh flight search results if on that tab
            self._search_flights_gui() 
        else:
            messagebox.showerror("Booking Failed", message)

    def _view_booking_gui(self):
        """Handles viewing booking details."""
        booking_id_str = self.booking_id_entry.get().strip()
        if not booking_id_str:
            messagebox.showerror("Input Error", "Please enter a Booking ID.")
            return

        try:
            booking_id = int(booking_id_str)
        except ValueError:
            messagebox.showerror("Invalid Input", "Booking ID must be an integer.")
            return

        booking_info = self.db_manager.get_booking(booking_id)
        if booking_info:
            b_id, dep, dest, date, time, p_name, n_seats, t_price, price_per_seat = booking_info
            details = (
                f"Booking ID: {b_id}\n"
                f"Flight: {dep} to {dest} on {date} at {time}\n"
                f"Passenger: {p_name}\n"
                f"Number of Seats: {n_seats}\n"
                f"Price per Seat: ${price_per_seat:.2f}\n"
                f"Total Price: ${t_price:.2f}"
            )
            self.booking_details_label.config(text=details)
        else:
            self.booking_details_label.config(text="Booking Details:\nBooking not found.")
            messagebox.showinfo("Booking Not Found", "No booking found with that ID.")

    def _cancel_booking_gui(self):
        """Handles cancelling a booking."""
        booking_id_str = self.booking_id_entry.get().strip()
        if not booking_id_str:
            messagebox.showerror("Input Error", "Please enter a Booking ID to cancel.")
            return

        try:
            booking_id = int(booking_id_str)
        except ValueError:
            messagebox.showerror("Invalid Input", "Booking ID must be an integer.")
            return

        if messagebox.askyesno("Confirm Cancellation", f"Are you sure you want to cancel booking ID {booking_id}?"):
            success, message = self.db_manager.cancel_booking(booking_id)
            if success:
                messagebox.showinfo("Cancellation Success", message)
                self.booking_details_label.config(text="Booking Details:\n") # Clear details
                self.booking_id_entry.delete(0, tk.END) # Clear input
                self._search_flights_gui() # Refresh flight results
            else:
                messagebox.showerror("Cancellation Failed", message)

    def _add_flight_gui(self):
        """Handles adding a new flight from the Admin tab."""
        departure = self.admin_departure_entry.get().strip()
        destination = self.admin_destination_entry.get().strip()
        date = self.admin_date_entry.get().strip()
        time = self.admin_time_entry.get().strip()
        price_str = self.admin_price_entry.get().strip()
        seats_str = self.admin_seats_available_entry.get().strip()

        if not all([departure, destination, date, time, price_str, seats_str]):
            messagebox.showerror("Input Error", "All fields are required to add a flight.")
            return

        if not self._is_valid_date(date):
            messagebox.showerror("Invalid Input", "Please enter date in YYYY-MM-DD format.")
            return

        if not self._is_valid_time(time):
            messagebox.showerror("Invalid Input", "Please enter time in HH:MM format (24-hour).")
            return

        try:
            price = float(price_str)
            seats = int(seats_str)
            if price <= 0 or seats <= 0:
                raise ValueError("Price and Seats must be positive values.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Price must be a valid number and Seats a valid integer.")
            return

        if self.db_manager.add_flight(departure, destination, date, time, price, seats):
            messagebox.showinfo("Flight Added", "New flight added successfully!")
            # Clear input fields
            for entry in self.admin_entries.values():
                entry.delete(0, tk.END)
            self._search_flights_gui() # Refresh search results

    # --- Utility Methods ---
    def _is_valid_date(self, date_str):
        """Checks if a string is a valid date in YYYY-MM-DD format."""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def _is_valid_time(self, time_str):
        """Checks if a string is a valid time in HH:MM format."""
        try:
            datetime.strptime(time_str, '%H:%M')
            return True
        except ValueError:
            return False

# --- Main execution block ---
if __name__ == "__main__":
    # This block ensures the application runs only when the script is executed directly
    # and handles the Tkinter event loop.
    app = AirlineApp()
    app.mainloop()
