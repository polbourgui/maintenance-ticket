from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.auth import RefreshTokenRepository
from app.repositories.providers import ProviderRepository
from app.repositories.tickets import TicketEventRepository, TicketPhotoRepository, TicketRepository
from app.repositories.users import SiteRepository, UserRepository


class UnitOfWork:
    """Groups the repositories sharing one transaction.

    New modules (stock, digital signatures...) add their repository here and get transactional
    consistency with tickets for free.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sites = SiteRepository(session)
        self.providers = ProviderRepository(session)
        self.tickets = TicketRepository(session)
        self.ticket_events = TicketEventRepository(session)
        self.ticket_photos = TicketPhotoRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
