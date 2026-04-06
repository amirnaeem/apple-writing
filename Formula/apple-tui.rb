class AppleTui < Formula
  desc "Privacy-first terminal interface to Apple's on-device Foundation Models"
  homepage "https://github.com/amirnaeem/apple-writing"
  url "https://github.com/amirnaeem/apple-writing/archive/refs/tags/v0.3.1.tar.gz"
  sha256 "1ec218213ff44ca854f2cbff65fc806da75ba7158111f899c065b8ab351e0a7a"
  license "MIT"
  version "0.3.1"

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
