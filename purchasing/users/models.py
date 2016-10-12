# -*- coding: utf-8 -*-
import random
from flask_security.utils import encrypt_password

from flask.ext.login import AnonymousUserMixin
from flask.ext.security import UserMixin, RoleMixin

from purchasing.database import Column, db, Model, ReferenceCol, SurrogatePK
from sqlalchemy.orm import backref

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('roles.id'))
)

def rand_alphabet():
    ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return encrypt_password(''.join(random.choice(ALPHABET) for i in range(16)))

class Role(SurrogatePK, RoleMixin, Model):
    '''Model to handle view-based permissions

    Attributes:
        id: primary key
        name: role name
        description: description of an individual role
    '''
    __tablename__ = 'roles'
    name = Column(db.String(80), unique=True, nullable=False)
    description = Column(db.String(255), nullable=True)

    def __repr__(self):
        return '<Role({name})>'.format(name=self.name)

    def __unicode__(self):
        return self.name

    @classmethod
    def query_factory(cls):
        '''Generates a query of all roles

        Returns:
            `sqla query`_ of all roles
        '''
        return cls.query

    @classmethod
    def no_admins(cls):
        '''Generates a query of non-admin roles

        Returns:
            `sqla query`_ of roles without administrative access
        '''
        return cls.query.filter(cls.name != 'superadmin')

    @classmethod
    def staff_factory(cls):
        '''Factory to return the staff role

        Returns:
            Role object with the name 'staff'
        '''
        return cls.query.filter(cls.name == 'staff')

class User(UserMixin, SurrogatePK, Model):
    '''User model

    Attributes:
        id: primary key
        email: user email address
        first_name: first name of user
        last_name: last name of user
        active: whether user is currently active or not
        roles: relationship of user to role table
        department_id: foreign key of user's department
        department: relationship of user to department table
    '''

    __tablename__ = 'users'
    email = Column(db.String(80), unique=True, nullable=False, index=True)
    first_name = Column(db.String(30), nullable=True)
    last_name = Column(db.String(30), nullable=True)
    active = Column(db.Boolean(), default=True)

    roles = db.relationship(
        'Role', secondary=roles_users,
        backref=backref('users', lazy='dynamic'),
    )

    department_id = ReferenceCol('department', ondelete='SET NULL', nullable=True)
    department = db.relationship(
        'Department', backref=backref('users', lazy='dynamic'),
        foreign_keys=department_id, primaryjoin='User.department_id==Department.id'
    )

    password = db.Column(db.String(255), nullable=False, default=rand_alphabet)

    confirmed_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    current_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(255))
    current_login_ip = db.Column(db.String(255))
    login_count = db.Column(db.Integer)

    def __repr__(self):
        return '<User({email!r})>'.format(email=self.email)

    def __unicode__(self):
        return self.email

    @property
    def role(self):
        if len(self.roles) > 0:
            return self.roles[0]
        return Role(name='')

    @property
    def full_name(self):
        '''Build full name of user

        Returns:
            concatenated string of first_name and last_name values
        '''
        return "{0} {1}".format(self.first_name, self.last_name)

    @classmethod
    def department_user_factory(cls, department_id):
        return cls.query.filter(
            cls.department_id == department_id,
            db.func.lower(Department.name) != 'equal opportunity review commission'
        )

    @classmethod
    def county_purchaser_factory(cls):
        return cls.query.filter(
            User.roles.any(Role.name == 'county')
        )

    @classmethod
    def eorc_user_factory(cls):
        return cls.query.join(
            Department, User.department_id == Department.id
        ).filter(
            db.func.lower(Department.name) == 'equal opportunity review commission'
        )

    @classmethod
    def get_subscriber_groups(cls, department_id):
        return [
            cls.department_user_factory(department_id).all(),
            cls.county_purchaser_factory().all(),
            cls.eorc_user_factory().all()
        ]

    def get_following(self):
        '''Generate user contract subscriptions

        Returns:
            list of ids for contracts followed by user
        '''
        return [i.id for i in self.contracts_following]

    def is_conductor(self):
        '''Check if user can access conductor application

        Returns:
            True if user's role is either conductor, admin, or superadmin,
            False otherwise
        '''
        return any([
            self.has_role('conductor'),
            self.has_role('admin'),
            self.has_role('superadmin')
        ])

    def is_admin(self):
        '''Check if user can access admin applications

        Returns:
            True if user's role is admin or superadmin, False otherwise
        '''
        return any([
            self.has_role('admin'), self.has_role('superadmin')
        ])

    def print_pretty_name(self):
        '''Generate long version text representation of user

        Returns:
            full_name if first_name and last_name exist, email otherwise
        '''
        if self.first_name and self.last_name:
            return self.full_name
        else:
            return self.email

    def print_pretty_first_name(self):
        '''Generate abbreviated text representation of user

        Returns:
            first_name if first_name exists,
            `localpart <https://en.wikipedia.org/wiki/Email_address#Local_part>`_
            otherwise
        '''
        if self.first_name:
            return self.first_name
        else:
            return self.email.split('@')[0]

    @classmethod
    def conductor_users_query(cls):
        '''Query users with access to conductor

        Returns:
            list of users with ``is_conductor`` value of True
        '''
        return [i for i in cls.query.all() if i.is_conductor()]


class Department(SurrogatePK, Model):
    '''Department model

    Attributes:
        name: Name of department
    '''
    __tablename__ = 'department'

    name = Column(db.String(255), nullable=False, unique=True)

    def __unicode__(self):
        return self.name

    @classmethod
    def query_factory(cls):
        '''Generate a department query factory.

        Returns:
            Department query with new users filtered out
        '''
        return cls.query.filter(cls.name != 'New User')

    @classmethod
    def get_dept(cls, dept_name):
        '''Query Department by name.

        Arguments:
            dept_name: name used for query

        Returns:
            an instance of Department
        '''
        return cls.query.filter(db.func.lower(cls.name) == dept_name.lower()).first()

    @classmethod
    def choices(cls, blank=False):
        '''Query available departments by name and id.

        Arguments:
            blank: adds none choice to list when True,
                only returns Departments when False. Defaults to False.

        Returns:
            list of (department id, department name) tuples
        '''
        departments = [(i.id, i.name) for i in cls.query_factory().all()]
        if blank:
            departments = [(None, '-----')] + departments
        return departments

class AnonymousUser(AnonymousUserMixin):
    '''Custom mixin for handling anonymous (non-logged-in) users

    Attributes:
        roles: List of a single
            :py:class:`~purchasing.user.models.Role`
            object with name set to 'anonymous'
        department: :py:class:`~purchasing.user.models.Department`
            object with name set to 'anonymous'
        id: Defaults to -1

    See Also:
        ``AnonymousUser`` subclasses the `flask_login anonymous user mixin
        <https://flask-login.readthedocs.org/en/latest/#anonymous-users>`_,
        which contains a number of class and instance methods around
        determining if users are currently logged in.
    '''
    roles = [Role(name='anonymous')]
    department = Department(name='anonymous')
    id = -1

    def __init__(self, *args, **kwargs):
        super(AnonymousUser, self).__init__(*args, **kwargs)

    def is_conductor(self):
        return False

    def is_admin(self):
        return False
