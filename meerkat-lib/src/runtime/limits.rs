//! System limits for Meerkat

/// Maximum allowed length of an identifier in characters
pub const MAX_IDENTIFIER_LENGTH: usize = 64;

/// Maximum allowed length of a string literal in characters
pub const MAX_STRING_LITERAL_LENGTH: usize = 8192;

/// Maximum allowed nesting depth of a type structure during deserialization
pub const MAX_TYPE_DEPTH: usize = 16;
