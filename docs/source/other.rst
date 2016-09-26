Other Components
================

Notifications
-------------

.. automodule:: purchasing.notifications
    :members:

.. _nightly-jobs:

Nightly Jobs
------------

.. autoclass:: purchasing.jobs.job_base.JobBase
    :members:

.. autoclass:: purchasing.jobs.job_base.EmailJobBase
    :members:

Admin
-----

For more information on how to use the admin, see the `Admin user's guide <https://docs.google.com/document/d/1fjPSmQxTxIkvcOT5RjtG69_oRFDoZGdOdcbQd85C3aI/export?format=pdf>`_. The admin is built using `Flask Admin <https://flask-admin.readthedocs.org/en/latest/>`_.

.. _persona:

User Logins
-----------

Users are handled using the `Flask-Security <http://flask-security.readthedocs.org/en/latest/>`_ framework. More on how this works will be made available soon.

.. _FileStorage: http://werkzeug.pocoo.org/docs/0.10/datastructures/#werkzeug.datastructures.FileStorage
.. _Message: https://pythonhosted.org/Flask-Mail/#flask_mail.Message
