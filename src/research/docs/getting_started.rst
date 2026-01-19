.. _getting_started:

Getting Started
==============

This guide will help you get started with AstraGuard AI, from installation to running your first simulation.

Prerequisites
------------
- Python 3.9 or higher
- pip (Python package manager)
- Git (for development)

Installation
------------

1. Clone the repository:
   .. code-block:: bash

      git clone https://github.com/sr-857/AstraGuard-AI.git
      cd AstraGuard-AI

2. Create and activate a virtual environment (recommended):
   .. code-block:: bash

      # On Windows
      python -m venv venv
      .\\venv\\Scripts\\activate

      # On macOS/Linux
      python3 -m venv venv
      source venv/bin/activate

3. Install dependencies:
   .. code-block:: bash

      pip install -r requirements.txt

Running the Dashboard
---------------------

1. Start the Streamlit dashboard:
   .. code-block:: bash

      streamlit run dashboard/app.py

2. Open your web browser to http://localhost:8501

Running the 3D Simulation
-------------------------

To run the 3D attitude simulation:
.. code-block:: bash

   python simulation/attitude_3d.py

First Steps
-----------

1. **Explore the Dashboard**
   - Monitor real-time telemetry
   - View system status
   - Check anomaly detection status

2. **Run a Simulation**
   - Start with normal operation
   - Inject test anomalies
   - Observe recovery actions

3. **Review Logs**
   - Check the event timeline
   - Review anomaly reports
   - Export data for analysis

Next Steps
----------
- Read the :ref:`user_guide` for detailed usage instructions
- Explore the :ref:`api` for developer documentation
- Check out the :ref:`architecture` for system design details
