# Homebrew formula for repofail
# To use: copy to your tap repo (e.g. homebrew-tap/Formula/repofail.rb)
# Then: brew tap jayvenn21/tap && brew install jayvenn21/tap/repofail
#
# Homebrew uses --no-deps when installing the main package, so all Python
# dependencies must be declared as resources below.
# If SHA256 fails after pushing a new tag, get the correct hash with:
#   curl -sL https://github.com/jayvenn21/repofail/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256

class Repofail < Formula
  include Language::Python::Virtualenv

  desc "Deterministic runtime compatibility analyzer"
  homepage "https://github.com/jayvenn21/repofail"
  url "https://github.com/jayvenn21/repofail/archive/refs/tags/v0.2.5.tar.gz"
  sha256 "ac1791fcfd24fd9a70df44423f02ac6f70df5df53ee2f2fca7d518a6b639fa86"
  license "MIT"

  # App supports Python 3.10+. We use 3.12 for current Homebrew; change to
  # python@3.10 or python@3.11 if you need an older interpreter.
  depends_on "libyaml"
  depends_on "python@3.12"

  resource "click" do
    url "https://files.pythonhosted.org/packages/3d/fa/656b739db8587d7b5dfa22e22ed02566950fbfbcdc20311993483657a5c0/click-8.3.1.tar.gz"
    sha256 "12ff4785d337a1bb490bb7e9c2b1ee5da3112e94a8622f26a6c77f5d2fc6842a"
  end

  resource "typer" do
    url "https://files.pythonhosted.org/packages/ac/0a/d55af35db5f50f486e3eda0ada747eed773859e2699d3ce570b682a9b70a/typer-0.12.3.tar.gz"
    sha256 "49e73131481d804288ef62598d97a1ceef3058905aa536a1134f90891ba35482"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/ab/3a/0316b28d0761c6734d6bc14e770d85506c986c85ffb239e688eeaab2c2bc/rich-13.9.4.tar.gz"
    sha256 "439594978a49a09530cff7ebc4b5c7103ef57baf48d5ea3184f21d9a2befa098"
  end

  resource "shellingham" do
    url "https://files.pythonhosted.org/packages/58/15/8b3609fd3830ef7b27b655beb4b4e9c62313a4e8da8c676e142cc210d58e/shellingham-1.5.4.tar.gz"
    sha256 "8dbca0739d487e5bd35ab3ca4b36e11c4078f3a234bfce294b0a0291363404de"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/df/db/f35a00659bc03fec321ba8bce9420de607a1d37f8342eee1863174c69557/typing_extensions-4.12.2.tar.gz"
    sha256 "1a7ead55c7e559dd4dee8856e3a88b41225abfe1ce8df57b7c13915fe121ffb8"
  end

  resource "tomli" do
    url "https://files.pythonhosted.org/packages/35/b9/de2a5c0144d7d75a57ff355c0c24054f965b2dc3036456ae03a51ea6264b/tomli-2.0.2.tar.gz"
    sha256 "d46d457a85337051c36524bc5349dd91b1877838e2979ac5ced3e710ed8a60ed"
  end

  resource "pyyaml" do
    url "https://github.com/yaml/pyyaml/archive/refs/tags/6.0.1.tar.gz"
    sha256 "57314c984aaa84318eed00cf5a8365afc49f87954969e295efe2ba99f3b21f7a"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "repofail", shell_output("#{bin}/repofail --help", 0)
  end
end
