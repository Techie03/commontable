// Live delivery map: the restaurant and the moving courier, rendered
// with Leaflet over OpenStreetMap tiles (no API key). The courier marker
// glides between pings instead of jumping. Loaded with ssr: false:
// Leaflet needs the browser window. The map never invents positions:
// a marker appears only for coordinates the backend actually reported.

"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { DriverLocation } from "@/lib/types";

export interface MapRestaurant {
  latitude: number;
  longitude: number;
  name?: string | null;
}

// Denton, TX: the pilot zone. Used only as the initial center when
// neither the restaurant nor the courier has coordinates yet.
const DENTON: [number, number] = [33.2148, -97.1331];
// Pings arrive every 5 seconds; the glide finishes just before the
// next one lands.
const GLIDE_MS = 4500;
// A jump this large is a first fix or a GPS jump, not a drive: snap.
const SNAP_KM = 2;

function distanceKm(
  a: [number, number],
  b: [number, number]
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

function courierIcon() {
  return L.divIcon({
    className: "app-map-marker",
    html: '<span class="app-map-courier" aria-label="Courier">🛵</span>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

function restaurantIcon(name?: string | null) {
  return L.divIcon({
    className: "app-map-marker",
    html: `<span class="app-map-restaurant" aria-label="${name ?? "Restaurant"}">🏪</span>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

export default function DeliveryMap({
  restaurant,
  driverLocation,
}: {
  restaurant?: MapRestaurant | null;
  driverLocation?: DriverLocation | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const courierRef = useRef<L.Marker | null>(null);
  const restaurantRef = useRef<L.Marker | null>(null);
  const meRef = useRef<L.CircleMarker | null>(null);
  const displayedRef = useRef<[number, number] | null>(null);
  const targetRef = useRef<[number, number] | null>(null);
  const rafRef = useRef<number | null>(null);
  const fittedRef = useRef(false);
  const [myLocationError, setMyLocationError] = useState<string | null>(null);

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const center: [number, number] =
      restaurant != null
        ? [restaurant.latitude, restaurant.longitude]
        : driverLocation != null
          ? [driverLocation.latitude, driverLocation.longitude]
          : DENTON;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
    }).setView(center, 14);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    mapRef.current = map;
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      map.remove();
      mapRef.current = null;
      courierRef.current = null;
      restaurantRef.current = null;
      meRef.current = null;
      fittedRef.current = false;
    };
    // The map is created once; later prop changes move markers below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restaurant marker.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (restaurant == null) return;
    if (!restaurantRef.current) {
      restaurantRef.current = L.marker(
        [restaurant.latitude, restaurant.longitude],
        { icon: restaurantIcon(restaurant.name) }
      ).addTo(map);
      if (restaurant.name) {
        restaurantRef.current.bindTooltip(restaurant.name);
      }
    } else {
      restaurantRef.current.setLatLng([
        restaurant.latitude,
        restaurant.longitude,
      ]);
    }
  }, [restaurant]);

  // Courier marker: glide toward each new ping.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || driverLocation == null) return;
    const target: [number, number] = [
      driverLocation.latitude,
      driverLocation.longitude,
    ];
    targetRef.current = target;
    if (!courierRef.current) {
      courierRef.current = L.marker(target, { icon: courierIcon() }).addTo(
        map
      );
      displayedRef.current = target;
    }
    const from = displayedRef.current ?? target;
    if (distanceKm(from, target) > SNAP_KM) {
      displayedRef.current = target;
      courierRef.current.setLatLng(target);
      return;
    }
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const started = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / GLIDE_MS);
      // Ease out: fast at first, settling as it arrives.
      const eased = 1 - (1 - t) * (1 - t);
      const lat = from[0] + (target[0] - from[0]) * eased;
      const lng = from[1] + (target[1] - from[1]) * eased;
      displayedRef.current = [lat, lng];
      courierRef.current?.setLatLng([lat, lng]);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
  }, [driverLocation]);

  // Fit the view once both points exist; afterwards follow the courier
  // only when it would leave the visible map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const points: [number, number][] = [];
    if (restaurant != null) {
      points.push([restaurant.latitude, restaurant.longitude]);
    }
    if (driverLocation != null) {
      points.push([driverLocation.latitude, driverLocation.longitude]);
    }
    if (points.length === 0) return;
    if (!fittedRef.current && points.length >= 2) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
      fittedRef.current = true;
      return;
    }
    if (fittedRef.current && driverLocation != null) {
      const pos = L.latLng(driverLocation.latitude, driverLocation.longitude);
      if (!map.getBounds().contains(pos)) {
        map.panTo(pos, { animate: true });
      }
    }
  }, [restaurant, driverLocation]);

  const showMyLocation = () => {
    const map = mapRef.current;
    if (!map) return;
    if (!("geolocation" in navigator)) {
      setMyLocationError("Your device cannot share its location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const at: [number, number] = [
          pos.coords.latitude,
          pos.coords.longitude,
        ];
        if (!meRef.current) {
          meRef.current = L.circleMarker(at, {
            radius: 8,
            color: "#fff",
            weight: 2,
            fillColor: "#0f766e",
            fillOpacity: 1,
          }).addTo(map);
          meRef.current.bindTooltip("You");
        } else {
          meRef.current.setLatLng(at);
        }
        setMyLocationError(null);
      },
      () => {
        setMyLocationError(
          "Could not read your location. Turn location on in your browser settings to see yourself on the map."
        );
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  return (
    <div className="app-map-wrap">
      <div
        ref={containerRef}
        className="app-map"
        role="img"
        aria-label="Live delivery map"
      />
      <div className="app-map-actions">
        <button
          type="button"
          className="app-btn app-btn-small app-btn-ghost"
          onClick={showMyLocation}
        >
          Show my location
        </button>
        {myLocationError && (
          <span className="app-muted">{myLocationError}</span>
        )}
      </div>
    </div>
  );
}
