class Dsmview < Formula
  include Language::Python::Virtualenv

  desc "TUI SSH monitor for Synology DSM 7.x"
  homepage "https://github.com/janvete/dsmview"
  url "https://github.com/janvete/dsmview/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"
  head "https://github.com/janvete/dsmview.git", branch: "main"

  depends_on "python@3.12"
  depends_on "rust" => :build      # cryptography wheels build dep on some platforms

  # PYTHON_RESOURCES_BEGIN
  # The release workflow regenerates the resource blocks below using
  # homebrew-pypi-poet whenever a new tag is pushed.
  resource "textual" do
    url "https://files.pythonhosted.org/packages/source/t/textual/textual-0.86.3.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "paramiko" do
    url "https://files.pythonhosted.org/packages/source/p/paramiko/paramiko-3.5.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "plotext" do
    url "https://files.pythonhosted.org/packages/source/p/plotext/plotext-5.3.2.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "textual-plotext" do
    url "https://files.pythonhosted.org/packages/source/t/textual-plotext/textual_plotext-0.2.1.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end
  # PYTHON_RESOURCES_END

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "dsmview", shell_output("#{bin}/dsmview --help")
  end
end
