# app/models/__init__.py

from app.database.core import Base

# Data/Products
from .product import Product, ProductEmbedding
from .usage import RAGUsageLog

# CRM & AI Platform
from .campaign import SearchCampaign
from .company import Company
from .leads import Lead
from .deal import Deal
from .communication import Interaction, ChatSession