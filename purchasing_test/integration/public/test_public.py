# -*- coding: utf-8 -*-

from purchasing_test.test_base import BaseTestCase
from purchasing_test.util import (
    insert_a_user, insert_a_role
)

class TestPublic(BaseTestCase):
    render_templates = True

    def setUp(self):
        super(TestPublic, self).setUp()
        # create a conductor and general staff person
        self.conductor_role_id = insert_a_role('conductor')
        self.staff_role_id = insert_a_role('staff')
        self.admin_role_id = insert_a_role('admin')
        self.conductor = insert_a_user(role=self.conductor_role_id)
        self.staff = insert_a_user(email='foo2@foo.com', role=self.staff_role_id)
        self.admin = insert_a_user(email='foo3@foo.com', role=self.admin_role_id)

    def test_public(self):
        public_view = self.client.get('/')
        self.assert200(public_view)
        self.assertTrue('<i class="fa fa-train fa-stack-1x fa-body-bg"></i>' not in public_view.data)
        self.assertTrue('<a class="navbar-link" href="/admin/">Admin</a>' not in public_view.data)

    def test_public_staff(self):
        self.login_user(self.staff)
        staff_view = self.client.get('/')
        self.assert200(staff_view)
        self.assertTrue('<i class="fa fa-train fa-stack-1x fa-body-bg"></i>' not in staff_view.data)
        self.assertTrue('<a class="navbar-link" href="/admin/">Admin</a>' not in staff_view.data)

    def test_public_conductor(self):
        self.login_user(self.conductor)
        conductor_view = self.client.get('/')
        self.assert200(conductor_view)
        self.assertTrue('<i class="fa fa-train fa-stack-1x fa-body-bg"></i>' in conductor_view.data)
        self.assertTrue('<a class="navbar-link" href="/admin/">Admin</a>' not in conductor_view.data)

    def test_public_admin(self):
        self.login_user(self.admin)
        admin_view = self.client.get('/')
        self.assert200(admin_view)
        self.assertTrue('<i class="fa fa-train fa-stack-1x fa-body-bg"></i>' in admin_view.data)
        self.assertTrue('<a class="navbar-link" href="/admin/">Admin</a>' in admin_view.data)
