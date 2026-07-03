//! HTML values as an abstract data type
//!
//! Outside this module, no code knows how an HTML value is represented.
//! Today it is backed by a single rendered string, but that is private:
//! callers construct an `Html` through [`Html::from_rendered`] and read it
//! back through [`Html::as_str`] or `Display`. This boundary lets the
//! representation change later (for example, a structured tree that can be
//! validated to catch errors earlier and mitigate injection) without
//! affecting any code outside this module.

use std::fmt;

/// An evaluated HTML value
///
/// The internal representation is deliberately private. See the module
/// documentation for the rationale behind treating HTML as an abstract
/// data type.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Html {
    /// The rendered markup
    ///
    /// Private on purpose: no code outside this module may depend on HTML
    /// being represented as a string.
    rendered: String,
}

impl Html {
    /// Construct an `Html` value from already-rendered markup
    ///
    /// Args:
    ///     `rendered` (`String`): The rendered markup text
    ///
    /// Returns:
    ///     `Html`: The constructed HTML value
    pub fn from_rendered(rendered: String) -> Self {
        Html { rendered }
    }

    /// Borrow the rendered markup as a string slice
    ///
    /// This is the read accessor used by the printer and the network codec.
    /// It exposes the rendered content without revealing that the value is
    /// stored as a string.
    ///
    /// Returns:
    ///     `&str`: The rendered markup
    pub fn as_str(&self) -> &str {
        &self.rendered
    }
}

/// Implement the `Display` trait for the `Html` type
///
/// Prints the rendered markup.
impl fmt::Display for Html {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.rendered)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Verify that an `Html` value round-trips its rendered content through
    /// the public accessor and `Display`.
    #[test]
    fn test_html_render_roundtrip() {
        let html = Html::from_rendered("<p>The count is 0.</p>".to_string());
        assert_eq!(html.as_str(), "<p>The count is 0.</p>");
        assert_eq!(html.to_string(), "<p>The count is 0.</p>");
    }

    /// Verify that equality is by rendered content.
    #[test]
    fn test_html_equality() {
        let a = Html::from_rendered("<b>x</b>".to_string());
        let b = Html::from_rendered("<b>x</b>".to_string());
        let c = Html::from_rendered("<b>y</b>".to_string());
        assert_eq!(a, b);
        assert_ne!(a, c);
    }
}
