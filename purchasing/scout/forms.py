# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm

from wtforms.fields import TextField, TextAreaField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange
from wtforms.ext.sqlalchemy.fields import QuerySelectField

from purchasing.data.contracts import ContractType

class SearchForm(FlaskForm):
    '''Form to handle Scout search and filter

    Attributes:
        q: Search term -- required
        company_name: Flag to include company name in search
        contract_description: Flag to include contract description
            in search
        line_item: Flag to include line item name in search
        financial_id: Flag to include financial ID in search
            archived: Flag to include archived
            :py:class:`~purchasing.data.contracts.ContractBase`
            objects in search
        contract_type: Filter to include only
            :py:class:`~purchasing.data.contracts.ContractBase` objects
            that match a certain
            :py:class:`~purchasing.data.contracts.ContractType`
    '''
    q = TextField('Search', validators=[DataRequired()])
    company_name = BooleanField()
    contract_description = BooleanField()
    contract_detail = BooleanField()
    line_item = BooleanField()
    financial_id = BooleanField()
    archived = BooleanField()
    contract_type = QuerySelectField(
        query_factory=ContractType.query_factory_all,
        get_pk=lambda i: i.id,
        get_label=lambda i: i.name,
        allow_blank=True, blank_text='Choose type of contract'
    )

    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)

class FeedbackForm(FlaskForm):
    '''Form to collect sender and body for Scout contract feedback

    Attributes:
        sender: Email address of sender
        body: Body of message, required
    '''
    sender = TextField(validators=[Email()], default='No email provided')
    body = TextAreaField(validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super(FeedbackForm, self).__init__(*args, **kwargs)


class NoteForm(FlaskForm):
    '''Form to allow users to write notes about contracts

    Attributes:
        note: Body of note
        user: ID of the :py:class:`~purchasing.users.models.User`
            who wrote the note
    '''
    note = TextAreaField(validators=[DataRequired()])
    user = IntegerField(validators=[DataRequired(), NumberRange(min=0)])

    def __init__(self, *args, **kwargs):
        super(NoteForm, self).__init__(*args, **kwargs)
