class AppleTui < Formula
  desc "Privacy-first terminal interface to Apple's on-device Foundation Models"
  homepage "https://github.com/amirnaeem/apple-writing"
  url "https://github.com/amirnaeem/apple-writing/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "4318e78b2098242c8396403c2998da81761f7d4eda56c1f2d94b479f7ff5f9d8"
  license "MIT"
  version "0.3.0"

  depends_on "python@3.11"
  depends_on :macos

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install_and_link buildpath
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/ai --version")
  end
end
