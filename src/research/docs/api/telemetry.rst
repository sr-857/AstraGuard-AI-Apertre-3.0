.. _telemetry_api:

Telemetry Module
===============

The telemetry module handles the generation and processing of spacecraft telemetry data.

.. automodule:: telemetry.telemetry_stream
   :members:
   :undoc-members:
   :show-inheritance:

Classes
-------

.. autoclass:: telemetry.telemetry_stream.TelemetryStream
   :members:
   :undoc-members:
   :show-inheritance:

   The main class for generating and managing telemetry data streams.

   .. automethod:: __init__
   .. automethod:: generate_telemetry
   .. automethod:: get_latest
   .. automethod:: start_stream
   .. automethod:: stop_stream

Functions
---------

.. autofunction:: telemetry.telemetry_stream.generate_sample_telemetry
   :noindex:

   Generate a single sample of telemetry data.

   :return: Dictionary containing telemetry data
   :rtype: dict

.. autofunction:: telemetry.telemetry_stream.simulate_telemetry_stream
   :noindex:

   Simulate a continuous stream of telemetry data.

   :param callback: Function to call with each new telemetry sample
   :type callback: callable
   :param interval: Time between samples in seconds
   :type interval: float
   :param duration: Total duration to run in seconds (None for infinite)
   :type duration: float, optional

Example Usage
------------

.. code-block:: python

   from telemetry.telemetry_stream import TelemetryStream
   import time

   # Create a telemetry stream
   telemetry = TelemetryStream()
   
   # Start the stream
   telemetry.start_stream()
   
   try:
       while True:
           # Get the latest telemetry
           data = telemetry.get_latest()
           print(f"Timestamp: {data['timestamp']}, Voltage: {data['voltage']}V")
           time.sleep(1)
   except KeyboardInterrupt:
       # Clean up
       telemetry.stop_stream()

Data Schema
-----------

Each telemetry sample contains the following fields:

.. list-table::
   :widths: 20 10 30
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - timestamp
     - float
     - Unix timestamp in seconds
   * - voltage
     - float
     - Bus voltage in volts
   * - current
     - float
     - System current in amps
   * - temperature
     - float
     - Temperature in °C
   * - gyro_x, gyro_y, gyro_z
     - float
     - Angular velocity in rad/s
   * - wheel_speed
     - float
     - Reaction wheel speed in RPM
   * - mode
     - str
     - Current system mode

Error Handling
-------------

The module raises the following exceptions:

.. autoexception:: telemetry.telemetry_stream.TelemetryError
   :show-inheritance:

   Base class for telemetry-related exceptions.

.. autoexception:: telemetry.telemetry_stream.StreamError
   :show-inheritance:

   Raised when there's an error with the telemetry stream.
