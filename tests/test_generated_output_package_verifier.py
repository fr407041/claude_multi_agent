from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_generated_output_package import verify_package


def write_valid_shopping_site(root: Path) -> None:
    site = root / "shopping-site"
    site.mkdir(parents=True)
    (site / "index.html").write_text(
        """<!doctype html>
<html>
  <head><link rel="stylesheet" href="styles.css"><title>Demo Shop</title></head>
  <body>
    <main>
      <h1>Demo Shop</h1>
      <section id="product-grid" class="product-grid">
        <article class="product-card"><h2>Coffee</h2><p class="price">$12</p><button data-product-id="coffee">Add to cart</button></article>
        <article class="product-card"><h2>Tea</h2><p class="price">$9</p><button data-product-id="tea">Add to cart</button></article>
        <article class="product-card"><h2>Mug</h2><p class="price">$15</p><button data-product-id="mug">Add to cart</button></article>
        <article class="product-card"><h2>Beans</h2><p class="price">$18</p><button data-product-id="beans">Add to cart</button></article>
      </section>
      <aside id="cart">Cart count: <span id="cart-count">0</span> Total: <span id="cart-total">$0</span></aside>
      <button id="checkout">Checkout demo only</button>
    </main>
    <script src="app.js"></script>
  </body>
</html>
""",
        encoding="utf-8",
    )
    (site / "styles.css").write_text(
        """.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.product-card { border: 1px solid #ddd; padding: 1rem; border-radius: 12px; }
button { cursor: pointer; }
""",
        encoding="utf-8",
    )
    (site / "app.js").write_text(
        """const products = {coffee: 12, tea: 9, mug: 15, beans: 18};
const cartItems = [];
function updateCart() {
  const cartCount = cartItems.length;
  const total = cartItems.reduce((sum, item) => sum + products[item], 0);
  document.querySelector('#cart-count').textContent = String(cartCount);
  document.querySelector('#cart-total').textContent = `$${total}`;
}
function addToCart(productId) {
  cartItems.push(productId);
  updateCart();
}
document.querySelectorAll('[data-product-id]').forEach((button) => {
  button.addEventListener('click', () => addToCart(button.dataset.productId));
});
document.querySelector('#checkout').addEventListener('click', () => {
  alert('Checkout stub: demo only, no real payment processing.');
});
""",
        encoding="utf-8",
    )
    (site / "README.md").write_text(
        "# Static shopping site demo\n\nOpen `index.html` in a browser to review the static demo. It has no real payment processing.\n",
        encoding="utf-8",
    )


class GeneratedOutputPackageVerifierTests(unittest.TestCase):
    def test_valid_shopping_site_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_valid_shopping_site(root)
            report = verify_package(root, "shopping-site")
        self.assertTrue(report["all_passed"], report["failed_checks"])
        self.assertEqual("", report["failure_category"])

    def test_missing_required_file_is_artifact_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_valid_shopping_site(root)
            (root / "shopping-site/app.js").unlink()
            report = verify_package(root, "shopping-site")
        self.assertFalse(report["all_passed"])
        self.assertEqual("ARTIFACT_NOT_CREATED_BY_MODEL", report["failure_category"])
        self.assertIn("shopping-site/app.js exists", report["failed_checks"])

    def test_no_checkout_stub_fails_contract_without_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_valid_shopping_site(root)
            (root / "shopping-site/app.js").write_text(
                (root / "shopping-site/app.js").read_text(encoding="utf-8").replace("Checkout stub: demo only, no real payment processing.", "Thank you"),
                encoding="utf-8",
            )
            report = verify_package(root, "shopping-site")
        self.assertFalse(report["all_passed"])
        self.assertEqual("ARTIFACT_CONTRACT_FAILED", report["failure_category"])


if __name__ == "__main__":
    unittest.main()
