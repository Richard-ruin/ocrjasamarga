"""
PyObjectId for Pydantic v2 compatibility
"""

from typing import Any, Dict
from bson import ObjectId
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

class PyObjectId(ObjectId):
    """
    Custom ObjectId field that works with Pydantic v2
    """
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        """
        Define the core schema for Pydantic v2
        """
        return core_schema.with_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function(str),
        )
    
    @classmethod
    def _validate(cls, value: Any, info=None) -> "PyObjectId":
        """
        Validate ObjectId value
        """
        if isinstance(value, ObjectId):
            return cls(value)
        elif isinstance(value, str):
            if ObjectId.is_valid(value):
                return cls(value)
            else:
                raise ValueError(f"Invalid ObjectId: {value}")
        else:
            raise TypeError(f"ObjectId expected, got {type(value)}")
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema_: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """
        Define JSON schema for documentation
        """
        return {
            "type": "string",
            "format": "objectid",
            "description": "MongoDB ObjectId",
            "examples": ["507f1f77bcf86cd799439011"]
        }