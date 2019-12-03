# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-18.04"

  config.vm.box = "django_tenants_bionic_beaver"

  config.vm.box_url = "https://app.vagrantup.com/bento/boxes/ubuntu-18.04/versions/201808.24.0/providers/virtualbox.box"

  config.vm.network :forwarded_port, guest: 8088, host: 8088
  config.vm.network :forwarded_port, guest: 22, host: 2222, id: "ssh", disabled: true
  config.vm.network :forwarded_port, guest: 22, host: 2020, auto_correct: true

  config.vm.provider "virtualbox" do |v|
      v.memory = 2048
      v.cpus = 2
    end
end
