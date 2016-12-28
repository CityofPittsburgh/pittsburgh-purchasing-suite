from purchasing_test.test_base import BaseTestCase
from purchasing.users.models import User
from purchasing_test.factories import (
    RoleFactory, AcceptedEmailDomainsFactory, UserFactory,
    DepartmentFactory
)

from purchasing_test.util import insert_a_role, insert_a_user

class TestUsers(BaseTestCase):
    render_templates = True

    def setUp(self):
        super(TestUsers, self).setUp()
        RoleFactory.create(name='staff')
        AcceptedEmailDomainsFactory.create(domain='foo.com')

    def test_no_register_bad_domain(self):
        post = self.client.post('/register', data=dict(
            email='bad@notgood.com',
            password='password',
            password_confirm='password'
        ))
        self.assertEquals(User.query.count(), 0)
        self.assert200(post)
        self.assertTrue('not a valid email domain! You must be associated with the city.' in post.data)

    def test_new_user_has_staff_role(self):
        self.client.post('/register', data=dict(
            email='email@foo.com',
            password='password',
            password_confirm='password'
        ))
        self.assertEquals(User.query.count(), 1)
        self.assertTrue(User.query.first().has_role('staff'))

    def test_profile_update(self):
        admin = insert_a_role('admin')
        department1 = DepartmentFactory.create()
        department2 = DepartmentFactory.create()
        user = insert_a_user(role=admin, department=department1)

        self.assertEquals(user.department, department1)
        self.login_user(user)

        self.client.post('/users/profile', data=dict(
            first_name='foo',
            last_name='bar',
            department=department2.id
        ))

        self.assertEquals(user.first_name, 'foo')
        self.assertEquals(user.last_name, 'bar')
        self.assertEquals(user.department, department2)
        self.assert_flashes('Updated your profile!', 'alert-success')
