"""
Admin Service - Database operations for keyword categories management
"""
from typing import List, Dict, Optional
from ..core.database import db
import logging

logger = logging.getLogger(__name__)


class AdminService:
    """Service for managing keyword categories and keywords"""

    @staticmethod
    async def get_all_categories() -> List[Dict]:
        """Get all keyword categories"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    categories = await connection.fetch(
                        """
                        SELECT category_key, category_en, category_es, category_fr,
                               icon, color, description, active, created_at
                        FROM keyword_categories
                        ORDER BY category_key
                    """
                )
                return [dict(category) for category in categories]
            else:
                # Supabase production
                if db.active_db and hasattr(db.active_db, 'client'):
                    result = db.active_db.client.table("keyword_categories").select(
                        "category_key, category_en, category_es, category_fr, icon, color, description, active, created_at"
                    ).order("category_key").execute()
                    return result.data if result.data else []
                else:
                    return []

        except Exception as e:
            logger.error(f"❌ Error getting categories: {str(e)}")
            return []

    @staticmethod
    async def get_keywords_by_category(category_key: str) -> List[Dict]:
        """Get all keywords for a specific category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    keywords = await connection.fetch(
                        """
                        SELECT keyword, language, weight, active, created_at
                        FROM category_keywords
                        WHERE category_key = $1
                        ORDER BY language, weight DESC, keyword
                        """,
                        category_key
                    )
                    return [dict(keyword) for keyword in keywords]
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    result = client.table("category_keywords").select(
                        "keyword, language, weight, active, created_at"
                    ).eq("category_key", category_key).order("language").order("weight", desc=True).order("keyword").execute()
                    return result.data if result.data else []
                else:
                    return []

        except Exception as e:
            logger.error(f"❌ Error getting keywords for {category_key}: {str(e)}")
            return []

    @staticmethod
    async def create_category(
        category_key: str,
        category_en: str,
        category_es: str = None,
        category_fr: str = None,
        icon: str = "fas fa-tag",
        color: str = "#6B7280",
        description: str = None
    ) -> bool:
        """Create a new keyword category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        """
                        INSERT INTO keyword_categories
                        (category_key, category_en, category_es, category_fr, icon, color, description, active, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, NOW())
                        """,
                        category_key, category_en, category_es, category_fr, icon, color, description
                    )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    client.table("keyword_categories").insert({
                        "category_key": category_key,
                        "category_en": category_en,
                        "category_es": category_es,
                        "category_fr": category_fr,
                        "icon": icon,
                        "color": color,
                        "description": description,
                        "active": True
                    }).execute()
                else:
                    return False

            logger.info(f"✅ Created category: {category_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating category {category_key}: {str(e)}")
            return False

    @staticmethod
    async def update_category(
        category_key: str,
        category_en: str = None,
        category_es: str = None,
        category_fr: str = None,
        icon: str = None,
        color: str = None,
        description: str = None,
        active: bool = None
    ) -> bool:
        """Update an existing keyword category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                updates = []
                values = []
                counter = 1

                if category_en is not None:
                    updates.append(f"category_en = ${counter}")
                    values.append(category_en)
                    counter += 1

                if category_es is not None:
                    updates.append(f"category_es = ${counter}")
                    values.append(category_es)
                    counter += 1

                if category_fr is not None:
                    updates.append(f"category_fr = ${counter}")
                    values.append(category_fr)
                    counter += 1

                if icon is not None:
                    updates.append(f"icon = ${counter}")
                    values.append(icon)
                    counter += 1

                if color is not None:
                    updates.append(f"color = ${counter}")
                    values.append(color)
                    counter += 1

                if description is not None:
                    updates.append(f"description = ${counter}")
                    values.append(description)
                    counter += 1

                if active is not None:
                    updates.append(f"active = ${counter}")
                    values.append(active)
                    counter += 1

                if not updates:
                    return True

                values.append(category_key)
                query = f"UPDATE keyword_categories SET {', '.join(updates)} WHERE category_key = ${counter}"

                async with db.pool.acquire() as connection:
                    await connection.execute(query, *values)
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()

                    # Build update dictionary
                    update_data = {}
                    if category_en is not None:
                        update_data["category_en"] = category_en
                    if category_es is not None:
                        update_data["category_es"] = category_es
                    if category_fr is not None:
                        update_data["category_fr"] = category_fr
                    if icon is not None:
                        update_data["icon"] = icon
                    if color is not None:
                        update_data["color"] = color
                    if description is not None:
                        update_data["description"] = description
                    if active is not None:
                        update_data["active"] = active

                    if not update_data:
                        return True

                    client.table("keyword_categories").update(update_data).eq("category_key", category_key).execute()
                else:
                    return False

            logger.info(f"✅ Updated category: {category_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating category {category_key}: {str(e)}")
            return False

    @staticmethod
    async def delete_category(category_key: str) -> bool:
        """Delete a keyword category (and its keywords)"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    async with connection.transaction():
                        # Delete keywords first
                        await connection.execute(
                            "DELETE FROM category_keywords WHERE category_key = $1",
                            category_key
                        )
                        # Delete category
                        await connection.execute(
                            "DELETE FROM keyword_categories WHERE category_key = $1",
                            category_key
                        )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    # Delete keywords first (CASCADE should handle this, but be explicit)
                    client.table("category_keywords").delete().eq("category_key", category_key).execute()
                    # Delete category
                    client.table("keyword_categories").delete().eq("category_key", category_key).execute()
                else:
                    return False

            logger.info(f"✅ Deleted category: {category_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting category {category_key}: {str(e)}")
            return False

    @staticmethod
    async def add_keyword(
        category_key: str,
        keyword: str,
        language: str = "en",
        weight: float = 1.0
    ) -> bool:
        """Add a keyword to a category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        """
                        INSERT INTO category_keywords (category_key, keyword, language, weight, active, created_at)
                        VALUES ($1, $2, $3, $4, TRUE, NOW())
                        ON CONFLICT (category_key, keyword, language)
                        DO UPDATE SET weight = $4, active = TRUE
                        """,
                        category_key, keyword.lower().strip(), language, weight
                    )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    # First try to update existing keyword
                    existing = client.table("category_keywords").select("id").eq(
                        "category_key", category_key
                    ).eq("keyword", keyword.lower().strip()).eq("language", language).execute()

                    if existing.data:
                        # Update existing keyword
                        client.table("category_keywords").update({
                            "weight": weight,
                            "active": True
                        }).eq("category_key", category_key).eq(
                            "keyword", keyword.lower().strip()
                        ).eq("language", language).execute()
                    else:
                        # Insert new keyword
                        client.table("category_keywords").insert({
                            "category_key": category_key,
                            "keyword": keyword.lower().strip(),
                            "language": language,
                            "weight": weight,
                            "active": True
                        }).execute()
                else:
                    return False

            logger.info(f"✅ Added keyword '{keyword}' to {category_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error adding keyword '{keyword}' to {category_key}: {str(e)}")
            return False

    @staticmethod
    async def update_keyword(category_key: str, keyword: str, language: str, weight: float) -> bool:
        """Update a keyword's weight in a category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        """
                        UPDATE category_keywords
                        SET weight = $4
                        WHERE category_key = $1 AND keyword = $2 AND language = $3
                        """,
                        category_key, keyword, language, weight
                    )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    client.table("category_keywords").update({
                        "weight": weight
                    }).eq("category_key", category_key).eq("keyword", keyword).eq("language", language).execute()
                else:
                    return False

            logger.info(f"✅ Updated keyword '{keyword}' in {category_key} with weight {weight}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating keyword '{keyword}' in {category_key}: {str(e)}")
            return False

    @staticmethod
    async def delete_keyword(category_key: str, keyword: str, language: str) -> bool:
        """Delete a keyword from a category"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        "DELETE FROM category_keywords WHERE category_key = $1 AND keyword = $2 AND language = $3",
                        category_key, keyword, language
                    )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    client.table("category_keywords").delete().eq(
                        "category_key", category_key
                    ).eq("keyword", keyword).eq("language", language).execute()
                else:
                    return False

            logger.info(f"✅ Deleted keyword '{keyword}' from {category_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting keyword '{keyword}' from {category_key}: {str(e)}")
            return False

    @staticmethod
    async def get_category_statistics() -> Dict:
        """Get statistics about categories and keywords"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    stats = await connection.fetchrow(
                        """
                        SELECT
                            COUNT(DISTINCT kc.category_key) as total_categories,
                            COUNT(DISTINCT kc.category_key) FILTER (WHERE kc.active = TRUE) as active_categories,
                            COUNT(ck.keyword) as total_keywords,
                            COUNT(ck.keyword) FILTER (WHERE ck.active = TRUE) as active_keywords,
                            COUNT(DISTINCT ck.language) as languages_count
                        FROM keyword_categories kc
                        LEFT JOIN category_keywords ck ON kc.category_key = ck.category_key
                        """
                    )
                    return dict(stats) if stats else {}
            else:
                # Supabase production - simplified version (no complex joins)
                if db.is_supabase():
                    client = db.get_supabase_client()

                    # Get category stats
                    categories_result = client.table("keyword_categories").select("category_key, active").execute()
                    categories = categories_result.data if categories_result.data else []

                    # Get keyword stats
                    keywords_result = client.table("category_keywords").select("keyword, language, active").execute()
                    keywords = keywords_result.data if keywords_result.data else []

                    # Calculate stats
                    total_categories = len(categories)
                    active_categories = len([c for c in categories if c.get('active', False)])
                    total_keywords = len(keywords)
                    active_keywords = len([k for k in keywords if k.get('active', False)])
                    languages_count = len(set(k.get('language', '') for k in keywords if k.get('language')))

                    return {
                        'total_categories': total_categories,
                        'active_categories': active_categories,
                        'total_keywords': total_keywords,
                        'active_keywords': active_keywords,
                        'languages_count': languages_count
                    }
                else:
                    return {}

        except Exception as e:
            logger.error(f"❌ Error getting category statistics: {str(e)}")
            return {}


# Global instance
admin_service = AdminService()